"""End-to-end tests for AcademicPublicationReader and real CALC-03 / ANA-01 export wiring."""

import csv
import datetime as dt
import io
from decimal import Decimal

import pytest
from access.models import AuditEvent, Role, RoleAssignment, Scope
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from academic.models import (
    AcademicTerm,
    Assessment,
    CalculationRun,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Grade,
    Institution,
    OutcomeScore,
    Program,
    ProgramCourse,
    ProgramMembership,
    ProgramOutcome,
    ProgramOutcomeSet,
    Publication,
    SyllabusAssessment,
)
from academic.services import (
    CalculationService,
    EnrollmentService,
    GradeBatchService,
    GradeService,
    InstructorAssignmentService,
    PublicationService,
    SyllabusService,
)

from .services import ReportExportService

pytestmark = pytest.mark.django_db
URL = "/api/v1/reports/exports/"
FIXED_NOW = dt.datetime(2026, 11, 15, 10, 30, tzinfo=dt.UTC)


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _enroll(offering, student, actor) -> Enrollment:
    RoleAssignment.objects.get_or_create(
        user=student,
        role=Role.objects.get(pk="student"),
        scope=Scope.objects.get(pk=offering.pk),
    )
    return EnrollmentService().create(offering=offering, student=student, actor=actor)


@pytest.fixture
def live_world(db):
    """Real academic + CALC-02 + CALC-03 pipeline with distinct score states and formula-like text."""
    user_model = get_user_model()
    admin = user_model.objects.create_user("exp01_admin")
    coord = user_model.objects.create_user("exp01_coord")
    other_coord = user_model.objects.create_user("exp01_other_coord")
    teacher = user_model.objects.create_user("exp01_teacher")
    student1 = user_model.objects.create_user("exp01_student1")
    student2 = user_model.objects.create_user("exp01_student2")
    unenrolled = user_model.objects.create_user("exp01_unenrolled")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="EXP01 University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="EXPU", name="EXP01 University")
    dept = Department.objects.create(institution=inst, code="CENG", name="Computer Engineering")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CENG301", title="Algorithms", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CENG-BS",
        title="Computer Engineering",
        status=Program.Status.ACTIVE,
    )
    other_program = Program.objects.create(
        department=dept,
        code="EEE-BS",
        title="Electrical Engineering",
        status=Program.Status.ACTIVE,
    )
    ProgramCourse.objects.create(
        program=program,
        course=course,
        effective_from="2026-01-01",
        status=ProgramCourse.Status.APPROVED,
    )

    RoleAssignment.objects.create(
        user=coord,
        role=Role.objects.get(pk="program-coordinator"),
        scope=Scope.objects.get(pk=program.pk),
    )
    RoleAssignment.objects.create(
        user=other_coord,
        role=Role.objects.get(pk="program-coordinator"),
        scope=Scope.objects.get(pk=other_program.pk),
    )

    for idx, stu in enumerate((student1, student2, unenrolled), start=1):
        ProgramMembership.objects.create(
            program=program,
            user=stu,
            student_number=f"2026010{idx}",
            admitted_term=term,
            status=ProgramMembership.Status.ACTIVE,
        )

    po_set = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="EXP01 Spec",
    )
    # PO-1 has a formula-like prefix to verify CSV injection escaping end-to-end.
    po1 = ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO-1",
        label="=CMD|Engineering Knowledge",
        description="Apply engineering knowledge.",
        source_url="https://example.edu/po-1",
        ordering=1,
    )
    po2 = ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO-2",
        label="+Design & Analysis",
        description="Design complex systems.",
        source_url="https://example.edu/po-2",
        ordering=2,
    )
    ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO-3",
        label="Unassessed Ethics",
        description="Not mapped to any LO in this offering.",
        source_url="https://example.edu/po-3",
        ordering=3,
    )
    po_set.status = ProgramOutcomeSet.Status.ACTIVE
    po_set.effective_date = dt.date(2026, 1, 1)
    po_set.activated_by = coord
    po_set.activated_at = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    po_set.save()

    offering = CourseOffering.objects.create(
        program=program, course=course, term=term, section="01"
    )
    InstructorAssignmentService().create(
        offering=offering, user=teacher, assignment_role="instructor", actor=admin
    )

    syl_svc = SyllabusService()
    syllabus = syl_svc.create(offering=offering)
    lo1 = syl_svc.add_learning_outcome(
        syllabus=syllabus, code="LO-1", description="Core algorithms", order=1
    )
    lo2 = syl_svc.add_learning_outcome(
        syllabus=syllabus, code="LO-2", description="Lab implementation", order=2
    )
    sa_hw = syl_svc.add_assessment(
        syllabus=syllabus,
        code="HW1",
        kind=SyllabusAssessment.Kind.HOMEWORK,
        order=1,
        max_points=Decimal("100.00"),
        is_required=True,
        is_active=True,
    )
    sa_lab = syl_svc.add_assessment(
        syllabus=syllabus,
        code="LAB1",
        kind=SyllabusAssessment.Kind.LAB,
        order=2,
        max_points=Decimal("100.00"),
        is_required=True,
        is_active=True,
    )
    syllabus = syl_svc.replace_assessment_lo_matrix(
        syllabus=syllabus,
        expected_revision=syllabus.mapping_revision,
        mappings=[
            {
                "assessment": sa_hw.pk,
                "learning_outcome": lo1.pk,
                "weight": Decimal("100.00"),
                "is_active": True,
            },
            {
                "assessment": sa_lab.pk,
                "learning_outcome": lo2.pk,
                "weight": Decimal("100.00"),
                "is_active": True,
            },
        ],
    )
    syllabus = syl_svc.replace_lo_po_matrix(
        syllabus=syllabus,
        expected_revision=syllabus.mapping_revision,
        mappings=[
            {
                "learning_outcome": lo1.pk,
                "program_outcome": po1.pk,
                "weight": 4,
                "is_active": True,
            },
            {
                "learning_outcome": lo2.pk,
                "program_outcome": po2.pk,
                "weight": 3,
                "is_active": True,
            },
        ],
    )
    syl_svc.set_po_contribution(syllabus=syllabus, program_outcome=po1, weight=4)
    syl_svc.set_po_contribution(syllabus=syllabus, program_outcome=po2, weight=3)
    syllabus = syl_svc.approve(syllabus=syllabus, actor=coord)

    asmt_hw = Assessment.objects.create(
        offering=offering,
        title="HW1",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    asmt_lab = Assessment.objects.create(
        offering=offering,
        title="LAB1",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )

    enr1 = _enroll(offering, student1, coord)
    enr2 = _enroll(offering, student2, coord)
    # Give unenrolled a student role in another offering or none; they are NOT enrolled in `offering`.
    other_offering_course = Course.objects.create(
        home_department=dept, code="EEE101", title="Circuits", ects=5, credits=3
    )
    ProgramCourse.objects.create(
        program=other_program,
        course=other_offering_course,
        effective_from="2026-01-01",
        status=ProgramCourse.Status.APPROVED,
    )
    other_offering = CourseOffering.objects.create(
        program=other_program, course=other_offering_course, term=term, section="01"
    )
    RoleAssignment.objects.create(
        user=unenrolled,
        role=Role.objects.get(pk="student"),
        scope=Scope.objects.get(pk=other_offering.pk),
    )

    batch = GradeBatchService().create(offering=offering, name="Final Release")
    # student1: HW1 = 0.00 (measured zero!), LAB1 = exempt (ALL_EXEMPT for PO-2), PO-3 = NOT_ASSESSED
    GradeService().create(
        enrollment=enr1,
        assessment=asmt_hw,
        batch=batch,
        state=Grade.State.SCORED,
        points_earned=Decimal("0.00"),
        actor=teacher,
    )
    GradeService().create(
        enrollment=enr1,
        assessment=asmt_lab,
        batch=batch,
        state=Grade.State.EXEMPT,
        points_earned=None,
        actor=teacher,
    )
    # student2: HW1 = 80.00, LAB1 = 90.00
    GradeService().create(
        enrollment=enr2,
        assessment=asmt_hw,
        batch=batch,
        state=Grade.State.SCORED,
        points_earned=Decimal("80.00"),
        actor=teacher,
    )
    GradeService().create(
        enrollment=enr2,
        assessment=asmt_lab,
        batch=batch,
        state=Grade.State.SCORED,
        points_earned=Decimal("90.00"),
        actor=teacher,
    )
    GradeBatchService().release(batch=batch, actor=coord)

    # Run offering calculation and publish for both faculty and student audiences.
    calc_svc = CalculationService()
    pub_svc = PublicationService()

    offering_run, _ = calc_svc.run_offering(offering=offering, actor=coord)
    faculty_pub, _ = pub_svc.publish(
        actor=coord,
        run=offering_run,
        expected_series_version=0,
        expected_input_hash=offering_run.input_hash,
        audience=Publication.Audience.FACULTY,
        idempotency_key="exp01-offering-faculty-v1",
    )
    student_pub, _ = pub_svc.publish(
        actor=coord,
        run=offering_run,
        expected_series_version=0,
        expected_input_hash=offering_run.input_hash,
        audience=Publication.Audience.STUDENT,
        idempotency_key="exp01-offering-student-v1",
    )

    # Also run program-level cumulative calculation and publish for students.
    program_run, _ = calc_svc.run_program(program=program, actor=coord)
    program_student_pub, _ = pub_svc.publish(
        actor=coord,
        run=program_run,
        expected_series_version=0,
        expected_input_hash=program_run.input_hash,
        audience=Publication.Audience.STUDENT,
        idempotency_key="exp01-program-student-v1",
        term=term,
    )

    return {
        "admin": admin,
        "coord": coord,
        "other_coord": other_coord,
        "teacher": teacher,
        "student1": student1,
        "student2": student2,
        "unenrolled": unenrolled,
        "program": program,
        "other_program": other_program,
        "offering": offering,
        "term": term,
        "enr1": enr1,
        "asmt_hw": asmt_hw,
        "offering_run": offering_run,
        "program_run": program_run,
        "faculty_pub": faculty_pub,
        "student_pub": student_pub,
        "program_student_pub": program_student_pub,
    }


def _parse_csv(content: bytes) -> list[list[str]]:
    text = content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def test_student_downloads_own_published_csv_and_pdf_with_distinct_states(live_world):
    pub = live_world["student_pub"]
    client = _client(live_world["student1"])

    csv_resp = client.get(
        URL,
        {"publication_id": str(pub.pk), "format": "csv", "scope": "student"},
    )
    assert csv_resp.status_code == 200
    assert csv_resp["Cache-Control"] == "no-store"
    assert csv_resp["Content-Disposition"].startswith(
        f'attachment; filename="outcome-report-student-{str(pub.pk)[:8]}.csv"'
    )

    rows = _parse_csv(csv_resp.content)
    meta = {r[0]: r[1] for r in rows if len(r) == 2}
    assert meta["Publication ID"] == str(pub.pk)
    assert meta["Run ID"] == str(pub.run_id)
    assert meta["PO-set version"] == "PO-set v1"
    assert meta["Freshness"] == "Current"

    po_rows = {r[0]: r for r in rows if len(r) == 6 and r[0].startswith("PO-")}
    # PO-1: measured 0.0 (distinct from missing!) and CSV formula prefix escaped with '
    assert po_rows["PO-1"][1] == "'=CMD|Engineering Knowledge"
    assert po_rows["PO-1"][2] == "0.0"
    assert po_rows["PO-1"][3] == "Measured"
    # PO-2: ALL_EXEMPT -> blank score + Exempt, and '+' prefix escaped
    assert po_rows["PO-2"][1] == "'+Design & Analysis"
    assert po_rows["PO-2"][2] == ""
    assert po_rows["PO-2"][3] == "Exempt"
    # PO-3: NOT_ASSESSED -> blank score + Not assessed
    assert po_rows["PO-3"][2] == ""
    assert po_rows["PO-3"][3] == "Not assessed"

    # Evidence section is present because student has released grades / evidence.view.
    assert any(r and r[0] == "PO" and len(r) == 9 and r[1] == "Formula" for r in rows)

    pdf_resp = client.get(
        URL,
        {"publication_id": str(pub.pk), "format": "pdf", "scope": "student"},
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp["Content-Type"] == "application/pdf"
    assert pdf_resp["Cache-Control"] == "no-store"
    assert pdf_resp["Content-Disposition"].startswith(
        f'attachment; filename="outcome-report-student-{str(pub.pk)[:8]}.pdf"'
    )
    assert pdf_resp.content.startswith(b"%PDF-")


def test_student_downloads_program_level_cumulative_publication(live_world):
    pub = live_world["program_student_pub"]
    client = _client(live_world["student2"])

    resp = client.get(
        URL,
        {"publication_id": str(pub.pk), "format": "csv", "scope": "student"},
    )
    assert resp.status_code == 200
    rows = _parse_csv(resp.content)
    po_rows = {r[0]: r for r in rows if len(r) == 6 and r[0].startswith("PO-")}
    assert po_rows["PO-1"][2] == "80.0"
    assert po_rows["PO-2"][2] == "90.0"
    assert po_rows["PO-3"][2] == ""
    assert po_rows["PO-3"][3] == "Not assessed"


def test_student_cannot_download_faculty_only_unpublished_or_other_students_pub(live_world):
    # 1. Faculty-only publication -> 404
    resp_faculty = _client(live_world["student1"]).get(
        URL,
        {
            "publication_id": str(live_world["faculty_pub"].pk),
            "format": "csv",
            "scope": "student",
        },
    )
    assert resp_faculty.status_code == 404

    # 2. Unpublished CalculationRun ID -> 404
    resp_unpub = _client(live_world["student1"]).get(
        URL,
        {
            "publication_id": str(live_world["offering_run"].pk),
            "format": "csv",
            "scope": "student",
        },
    )
    assert resp_unpub.status_code == 404

    # 3. Student not in that publication -> 404
    resp_other = _client(live_world["unenrolled"]).get(
        URL,
        {
            "publication_id": str(live_world["student_pub"].pk),
            "format": "csv",
            "scope": "student",
        },
    )
    assert resp_other.status_code == 404
    assert not AuditEvent.objects.filter(action="reports.exported").exists()


def test_coordinator_downloads_cohort_csv_and_pdf_with_audit_event(live_world):
    pub = live_world["faculty_pub"]
    program = live_world["program"]
    client = _client(live_world["coord"])

    csv_resp = client.get(
        URL,
        {
            "publication_id": str(pub.pk),
            "format": "csv",
            "scope": "cohort",
            "program_id": str(program.pk),
        },
    )
    assert csv_resp.status_code == 200
    assert csv_resp["Cache-Control"] == "no-store"
    rows = _parse_csv(csv_resp.content)
    meta = {r[0]: r[1] for r in rows if len(r) == 2}
    assert meta["Publication ID"] == str(pub.pk)
    assert meta["Run ID"] == str(pub.run_id)
    assert meta["PO-set version"] == "PO-set v1"
    assert meta["Sample size"] == "2"
    assert meta["Coverage"] == "0.5000"

    po_rows = {r[0]: r for r in rows if len(r) == 6 and r[0].startswith("PO-")}
    # PO-1 mean of 0.0 and 80.0 = 40.0, n=2, population=2
    assert po_rows["PO-1"][2] == "40.0"
    assert po_rows["PO-1"][3] == "Measured"
    assert po_rows["PO-1"][4] == "2"
    assert po_rows["PO-1"][5] == "2"
    # PO-2: student1 exempt, student2 90.0 -> mean=90.0, n=1, population=2
    assert po_rows["PO-2"][2] == "90.0"
    assert po_rows["PO-2"][4] == "1"
    assert po_rows["PO-2"][5] == "2"
    # PO-3: not assessed for both -> blank, Not assessed, n=0, population=2
    assert po_rows["PO-3"][2] == ""
    assert po_rows["PO-3"][3] == "Not assessed"
    assert po_rows["PO-3"][4] == "0"

    pdf_resp = client.get(
        URL,
        {
            "publication_id": str(pub.pk),
            "format": "pdf",
            "scope": "cohort",
            "program_id": str(program.pk),
        },
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF-")

    events = AuditEvent.objects.filter(actor=live_world["coord"], action="reports.exported")
    assert events.count() == 2
    assert {e.metadata["format"] for e in events} == {"csv", "pdf"}

    # Coordinator of another program gets 404
    denied = _client(live_world["other_coord"]).get(
        URL,
        {
            "publication_id": str(pub.pk),
            "format": "csv",
            "scope": "cohort",
            "program_id": str(program.pk),
        },
    )
    assert denied.status_code == 404


def test_incomplete_state_is_distinct_from_zero_and_reexports_are_reproducible(live_world):
    pub = live_world["student_pub"]
    # Add an INCOMPLETE OutcomeScore row on a separate publication snapshot check:
    # verify via direct OutcomeScore with status=INCOMPLETE on a fresh run/pub?
    # Even simpler: verify reproducibility first on the existing immutable publication.
    svc = ReportExportService(actor=live_world["coord"], clock=lambda: FIXED_NOW)
    for fmt in ("csv", "pdf"):
        first = svc.export(
            publication_id=pub.pk,
            format=fmt,
            scope="cohort",
            program_id=live_world["program"].pk,
        )
        second = svc.export(
            publication_id=pub.pk,
            format=fmt,
            scope="cohort",
            program_id=live_world["program"].pk,
        )
        assert first.content == second.content

    # Mutate a grade after publication -> publication becomes stale without mutating Publication row.
    grade = Grade.objects.get(enrollment=live_world["enr1"], assessment=live_world["asmt_hw"])
    GradeService().correct(
        grade=grade,
        expected_version=grade.version,
        state=Grade.State.SCORED,
        points_earned=Decimal("50.00"),
        reason="Regrade after review",
        actor=live_world["teacher"],
    )
    stale_export = svc.export(
        publication_id=pub.pk,
        format="csv",
        scope="cohort",
        program_id=live_world["program"].pk,
    )
    rows = _parse_csv(stale_export.content)
    meta = {r[0]: r[1] for r in rows if len(r) == 2}
    assert meta["Freshness"] == "Stale"
    # Immutable snapshot still reports the original 40.0 mean (not the mutated 65.0).
    po_rows = {r[0]: r for r in rows if len(r) == 6 and r[0].startswith("PO-")}
    assert po_rows["PO-1"][2] == "40.0"

    # Also verify INCOMPLETE state mapping in AcademicPublicationReader directly.
    incomplete_run = CalculationRun.objects.create(
        scope_kind=CalculationRun.ScopeKind.OFFERING,
        program=live_world["program"],
        offering=live_world["offering"],
        po_set_version=1,
        engine_version=live_world["offering_run"].engine_version,
        policy_version=live_world["offering_run"].policy_version,
        input_hash="a" * 64,
        manifest={},
        status=CalculationRun.Status.COMPLETED,
        is_complete_for_publication=False,
    )
    OutcomeScore.objects.create(
        run=incomplete_run,
        level=OutcomeScore.Level.COURSE_PO,
        student=live_world["student1"],
        offering=live_world["offering"],
        outcome_code="PO-4",
        value=None,
        status=OutcomeScore.Status.INCOMPLETE,
        evidence={},
    )
    incomplete_pub = Publication.objects.create(
        program=live_world["program"],
        offering=live_world["offering"],
        term=live_world["term"],
        run=incomplete_run,
        series_version=2,
        po_set_version=1,
        audience=Publication.Audience.STUDENT,
        input_hash="a" * 64,
        idempotency_key="exp01-incomplete-check",
        published_by=live_world["coord"],
    )
    student_svc = ReportExportService(actor=live_world["student1"], clock=lambda: FIXED_NOW)
    inc_csv = student_svc.export(publication_id=incomplete_pub.pk, format="csv", scope="student")
    inc_rows = _parse_csv(inc_csv.content)
    inc_po = {r[0]: r for r in inc_rows if len(r) == 6 and r[0] == "PO-4"}
    assert inc_po["PO-4"][2] == ""
    assert inc_po["PO-4"][3] == "Incomplete"
