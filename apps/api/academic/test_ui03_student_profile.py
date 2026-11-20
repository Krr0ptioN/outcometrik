"""Backend security & contract tests for UI-03 Student PO profile and explanation."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from access.models import Role, RoleAssignment, Scope
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from academic.models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Grade,
    Institution,
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


def _client(user=None) -> APIClient:
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _enroll(offering, student, actor):
    RoleAssignment.objects.get_or_create(
        user=student,
        role=Role.objects.get(pk="student"),
        scope=Scope.objects.get(pk=offering.pk),
    )
    return EnrollmentService().create(offering=offering, student=student, actor=actor)


@pytest.fixture
def ui03_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("ui03_admin")
    coord = user_model.objects.create_user("ui03_coord")
    teacher = user_model.objects.create_user("ui03_teacher")
    student1 = user_model.objects.create_user("ui03_student1")
    student2 = user_model.objects.create_user("ui03_student2")
    outsider = user_model.objects.create_user("ui03_outsider")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="UI03 University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="UI03U", name="UI03 University")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )

    course1 = Course.objects.create(
        home_department=dept, code="CSE311", title="Software Engineering", ects=6, credits=4
    )
    course2 = Course.objects.create(
        home_department=dept, code="CSE321", title="Database Systems", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CSE-BS",
        title="B.S. in Computer Engineering",
        status=Program.Status.ACTIVE,
    )
    for course in (course1, course2):
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

    for idx, stu in enumerate((student1, student2, outsider), start=1):
        ProgramMembership.objects.create(
            program=program,
            user=stu,
            student_number=f"2026030{idx}",
            admitted_term=term,
            status=ProgramMembership.Status.ACTIVE,
        )

    po_set = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="Acibadem CSE PO Set v1",
    )
    pos = {}
    for idx in range(1, 12):
        code = f"PO{idx}"
        pos[code] = ProgramOutcome.objects.create(
            outcome_set=po_set,
            code=code,
            label=f"Program Outcome {idx}",
            description=f"Authoritative description for {code}.",
            source_url=f"https://example.edu/{code.lower()}",
            ordering=idx,
        )
    po_set.status = ProgramOutcomeSet.Status.ACTIVE
    po_set.effective_date = dt.date(2026, 1, 1)
    po_set.activated_by = coord
    po_set.activated_at = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    po_set.save()

    offering1 = CourseOffering.objects.create(
        program=program, course=course1, term=term, section="A"
    )
    offering2 = CourseOffering.objects.create(
        program=program, course=course2, term=term, section="A"
    )
    for off in (offering1, offering2):
        InstructorAssignmentService().create(
            offering=off, user=teacher, assignment_role="instructor", actor=admin
        )

    # Offering 1 syllabus: canonical PRD §5 scenario (Midterm=90, Project=80 -> LO1=86.0, LO2=82.9, PO1=85.0, PO2=82.9)
    syl_svc = SyllabusService()
    syl1 = syl_svc.create(offering=offering1)
    lo1 = syl_svc.add_learning_outcome(
        syllabus=syl1, code="LO1", description="Analyze requirements", order=1
    )
    lo2 = syl_svc.add_learning_outcome(
        syllabus=syl1, code="LO2", description="Build software systems", order=2
    )
    sa_mid = syl_svc.add_assessment(
        syllabus=syl1,
        code="Midterm",
        kind=SyllabusAssessment.Kind.EXAM,
        order=1,
        max_points=Decimal("100.00"),
        is_required=True,
        is_active=True,
    )
    sa_proj = syl_svc.add_assessment(
        syllabus=syl1,
        code="Project",
        kind=SyllabusAssessment.Kind.PROJECT,
        order=2,
        max_points=Decimal("100.00"),
        is_required=True,
        is_active=True,
    )
    syl1 = syl_svc.replace_assessment_lo_matrix(
        syllabus=syl1,
        expected_revision=syl1.mapping_revision,
        mappings=[
            {"assessment": sa_mid.pk, "learning_outcome": lo1.pk, "weight": Decimal("60.00")},
            {"assessment": sa_proj.pk, "learning_outcome": lo1.pk, "weight": Decimal("40.00")},
            {"assessment": sa_mid.pk, "learning_outcome": lo2.pk, "weight": Decimal("40.00")},
            {"assessment": sa_proj.pk, "learning_outcome": lo2.pk, "weight": Decimal("100.00")},
        ],
    )
    syl1 = syl_svc.replace_lo_po_matrix(
        syllabus=syl1,
        expected_revision=syl1.mapping_revision,
        mappings=[
            {"learning_outcome": lo1.pk, "program_outcome": pos["PO1"].pk, "weight": 2},
            {"learning_outcome": lo2.pk, "program_outcome": pos["PO1"].pk, "weight": 1},
            {"learning_outcome": lo2.pk, "program_outcome": pos["PO2"].pk, "weight": 1},
        ],
    )
    syl_svc.set_po_contribution(syllabus=syl1, program_outcome=pos["PO1"], weight=4)
    syl_svc.set_po_contribution(syllabus=syl1, program_outcome=pos["PO2"], weight=3)
    syl1 = syl_svc.approve(syllabus=syl1, actor=coord)

    asmt_mid = Assessment.objects.create(
        offering=offering1,
        title="Midterm",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    asmt_proj = Assessment.objects.create(
        offering=offering1,
        title="Project",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )

    enr1 = _enroll(offering1, student1, coord)
    batch1 = GradeBatchService().create(offering=offering1, name="CSE311 Final Release")
    grade_mid = GradeService().create(
        enrollment=enr1,
        assessment=asmt_mid,
        batch=batch1,
        state=Grade.State.SCORED,
        points_earned=Decimal("90.00"),
        actor=teacher,
    )
    GradeService().create(
        enrollment=enr1,
        assessment=asmt_proj,
        batch=batch1,
        state=Grade.State.SCORED,
        points_earned=Decimal("80.00"),
        actor=teacher,
    )
    GradeBatchService().release(batch=batch1, actor=coord)

    # Offering 2: ONLY student2 is enrolled (to test cross-student publication isolation).
    syl2 = syl_svc.create(offering=offering2)
    lo2_1 = syl_svc.add_learning_outcome(
        syllabus=syl2, code="LO1", description="Design relational schemas", order=1
    )
    sa_hw = syl_svc.add_assessment(
        syllabus=syl2,
        code="HW1",
        kind=SyllabusAssessment.Kind.HOMEWORK,
        order=1,
        max_points=Decimal("100.00"),
        is_required=True,
        is_active=True,
    )
    syl2 = syl_svc.replace_assessment_lo_matrix(
        syllabus=syl2,
        expected_revision=syl2.mapping_revision,
        mappings=[
            {"assessment": sa_hw.pk, "learning_outcome": lo2_1.pk, "weight": Decimal("100.00")},
        ],
    )
    syl2 = syl_svc.replace_lo_po_matrix(
        syllabus=syl2,
        expected_revision=syl2.mapping_revision,
        mappings=[
            {"learning_outcome": lo2_1.pk, "program_outcome": pos["PO3"].pk, "weight": 5},
        ],
    )
    syl_svc.set_po_contribution(syllabus=syl2, program_outcome=pos["PO3"], weight=5)
    syl2 = syl_svc.approve(syllabus=syl2, actor=coord)

    asmt_hw = Assessment.objects.create(
        offering=offering2,
        title="HW1",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    enr2 = _enroll(offering2, student2, coord)
    batch2 = GradeBatchService().create(offering=offering2, name="CSE321 Final Release")
    GradeService().create(
        enrollment=enr2,
        assessment=asmt_hw,
        batch=batch2,
        state=Grade.State.SCORED,
        points_earned=Decimal("77.00"),
        actor=teacher,
    )
    GradeBatchService().release(batch=batch2, actor=coord)

    return {
        "coord": coord,
        "teacher": teacher,
        "student1": student1,
        "student2": student2,
        "outsider": outsider,
        "program": program,
        "term": term,
        "offering1": offering1,
        "offering2": offering2,
        "grade_mid": grade_mid,
    }


def test_student_profile_contract_all_11_pos_and_immutable_evidence_chain(ui03_world):
    calc_svc = CalculationService()
    pub_svc = PublicationService()

    prog_run, _ = calc_svc.run_program(program=ui03_world["program"], actor=ui03_world["coord"])
    prog_pub, _ = pub_svc.publish(
        actor=ui03_world["coord"],
        run=prog_run,
        expected_series_version=0,
        expected_input_hash=prog_run.input_hash,
        audience=Publication.Audience.STUDENT,
        idempotency_key="ui03-prog-v1",
        term=ui03_world["term"],
    )

    stu1_client = _client(ui03_world["student1"])
    pub_list_resp = stu1_client.get("/api/v1/publications/")
    assert pub_list_resp.status_code == 200
    assert pub_list_resp["Cache-Control"] == "no-store"

    results = pub_list_resp.json()["results"]
    assert len(results) == 1
    pub_data = results[0]
    assert pub_data["id"] == str(prog_pub.pk)
    assert pub_data["audience"] == "student"
    assert pub_data["scope_kind"] == "program"
    assert pub_data["series_version"] == 1
    assert pub_data["po_set_version"] == 1
    assert pub_data["stale"] is False
    assert pub_data["program_code"] == "CSE-BS"
    assert pub_data["term_label"] == "2026 Fall"
    assert [po["code"] for po in pub_data["program_outcomes"]] == [f"PO{i}" for i in range(1, 12)]

    scores_resp = stu1_client.get(f"/api/v1/publications/{prog_pub.pk}/scores/")
    assert scores_resp.status_code == 200
    assert scores_resp["Cache-Control"] == "no-store"
    rows = scores_resp.json()
    assert len(rows) == 11
    by_code = {row["outcome_code"]: row for row in rows}

    # Canonical PRD §5 values on PO1 & PO2; PO3–PO11 are NOT_ASSESSED with value=None (never 0).
    assert by_code["PO1"]["status"] == "OK"
    assert by_code["PO1"]["display_value"] == "85.0"
    assert by_code["PO2"]["status"] == "OK"
    assert by_code["PO2"]["display_value"] == "82.9"
    for idx in range(3, 12):
        unassessed = by_code[f"PO{idx}"]
        assert unassessed["status"] == "NOT_ASSESSED"
        assert unassessed["value"] is None
        assert unassessed["display_value"] is None

    # Full immutable evidence chain: cumulative PO -> course -> LO -> assessment -> normalized grade/weight.
    po1_courses = by_code["PO1"]["evidence"]["contributions"]
    assert len(po1_courses) == 1
    course_contrib = po1_courses[0]
    assert course_contrib["course_code"] == "CSE311"
    assert course_contrib["weight"] == "4"
    lo_contribs = course_contrib["lo_contributions"]
    assert {lo["lo_code"] for lo in lo_contribs} == {"LO1", "LO2"}
    lo1_contrib = next(lo for lo in lo_contribs if lo["lo_code"] == "LO1")
    lo1_assessments = lo1_contrib["assessment_contributions"]
    assert {a["assessment_code"] for a in lo1_assessments} == {"Midterm", "Project"}
    midterm_ev = next(a for a in lo1_assessments if a["assessment_code"] == "Midterm")
    assert midterm_ev["points_earned"] == "90"
    assert midterm_ev["points_possible"] == "100"
    assert midterm_ev["normalized_score"] == "90"
    assert midterm_ev["weight"] == "60"
    assert midterm_ev["grade_version"] == 1


def test_direct_object_and_url_manipulation_blocks_cross_student_and_draft_access(ui03_world):
    calc_svc = CalculationService()
    pub_svc = PublicationService()

    # Offering 2 only has student2 enrolled.
    off2_run, _ = calc_svc.run_offering(offering=ui03_world["offering2"], actor=ui03_world["coord"])
    off2_pub, _ = pub_svc.publish(
        actor=ui03_world["coord"],
        run=off2_run,
        expected_series_version=0,
        expected_input_hash=off2_run.input_hash,
        audience=Publication.Audience.STUDENT,
        idempotency_key="ui03-off2-stu-v1",
    )
    # Offering 1 faculty-only publication + unpublished draft run.
    off1_run, _ = calc_svc.run_offering(offering=ui03_world["offering1"], actor=ui03_world["coord"])
    fac_pub, _ = pub_svc.publish(
        actor=ui03_world["coord"],
        run=off1_run,
        expected_series_version=0,
        expected_input_hash=off1_run.input_hash,
        audience=Publication.Audience.FACULTY,
        idempotency_key="ui03-off1-fac-v1",
    )
    # Program publication containing both student1 and student2.
    prog_run, _ = calc_svc.run_program(program=ui03_world["program"], actor=ui03_world["coord"])
    prog_pub, _ = pub_svc.publish(
        actor=ui03_world["coord"],
        run=prog_run,
        expected_series_version=0,
        expected_input_hash=prog_run.input_hash,
        audience=Publication.Audience.STUDENT,
        idempotency_key="ui03-prog-sec-v1",
    )

    stu1_client = _client(ui03_world["student1"])
    outsider_client = _client(ui03_world["outsider"])
    anon_client = _client()

    # Unauthenticated requests are denied.
    assert anon_client.get("/api/v1/publications/").status_code in (401, 403)
    assert anon_client.get(f"/api/v1/publications/{prog_pub.pk}/scores/").status_code in (401, 403)

    # Student1 cannot access student2's offering publication, faculty publication, random UUID, or raw runs.
    assert stu1_client.get(f"/api/v1/publications/{off2_pub.pk}/").status_code == 404
    assert stu1_client.get(f"/api/v1/publications/{off2_pub.pk}/scores/").status_code == 404
    assert stu1_client.get(f"/api/v1/publications/{fac_pub.pk}/").status_code == 404
    assert stu1_client.get(f"/api/v1/publications/{fac_pub.pk}/scores/").status_code == 404
    assert stu1_client.get(f"/api/v1/publications/{uuid.uuid4()}/scores/").status_code == 404
    assert stu1_client.get("/api/v1/calculation-runs/").json()["results"] == []
    assert stu1_client.get(f"/api/v1/calculation-runs/{off1_run.pk}/").status_code == 404

    # URL query parameter manipulation (?student=student2 or ?student_id=student2) never leaks student2.
    for param in ("student", "student_id"):
        resp = stu1_client.get(
            f"/api/v1/publications/{prog_pub.pk}/scores/?{param}={ui03_world['student2'].pk}"
        )
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 11
        assert {row["student"] for row in rows} == {ui03_world["student1"].pk}
        # Student2 has PO3=77.0, while Student1 has PO3=NOT_ASSESSED; confirm no leak.
        po3 = next(row for row in rows if row["outcome_code"] == "PO3")
        assert po3["status"] == "NOT_ASSESSED"
        assert po3["value"] is None

    # Outsider with no enrollment sees no publications and gets 404 on detail/scores.
    assert outsider_client.get("/api/v1/publications/").json()["results"] == []
    assert outsider_client.get(f"/api/v1/publications/{prog_pub.pk}/").status_code == 404
    assert outsider_client.get(f"/api/v1/publications/{prog_pub.pk}/scores/").status_code == 404


def test_grade_correction_marks_publication_stale_without_rewriting_history(ui03_world):
    calc_svc = CalculationService()
    pub_svc = PublicationService()

    prog_run, _ = calc_svc.run_program(program=ui03_world["program"], actor=ui03_world["coord"])
    prog_pub, _ = pub_svc.publish(
        actor=ui03_world["coord"],
        run=prog_run,
        expected_series_version=0,
        expected_input_hash=prog_run.input_hash,
        audience=Publication.Audience.STUDENT,
        idempotency_key="ui03-stale-v1",
    )

    stu1_client = _client(ui03_world["student1"])
    before_pub = stu1_client.get(f"/api/v1/publications/{prog_pub.pk}/").json()
    assert before_pub["stale"] is False
    before_po1 = next(
        row
        for row in stu1_client.get(f"/api/v1/publications/{prog_pub.pk}/scores/").json()
        if row["outcome_code"] == "PO1"
    )
    assert before_po1["display_value"] == "85.0"

    # Instructor corrects Midterm from 90 -> 50 after publication.
    GradeService().correct(
        grade=ui03_world["grade_mid"],
        expected_version=ui03_world["grade_mid"].version,
        state=Grade.State.SCORED,
        points_earned=Decimal("50.00"),
        reason="Regrade after review",
        actor=ui03_world["teacher"],
    )

    after_pub = stu1_client.get(f"/api/v1/publications/{prog_pub.pk}/").json()
    assert after_pub["stale"] is True

    # Historical score and evidence remain completely unchanged (still 85.0 and Midterm=90).
    after_po1 = next(
        row
        for row in stu1_client.get(f"/api/v1/publications/{prog_pub.pk}/scores/").json()
        if row["outcome_code"] == "PO1"
    )
    assert after_po1["display_value"] == "85.0"
    assert after_po1["value"] == before_po1["value"]
    lo1_contrib = next(
        lo
        for lo in after_po1["evidence"]["contributions"][0]["lo_contributions"]
        if lo["lo_code"] == "LO1"
    )
    lo1_assessments = lo1_contrib["assessment_contributions"]
    midterm_ev = next(a for a in lo1_assessments if a["assessment_code"] == "Midterm")
    assert midterm_ev["points_earned"] == "90"
    assert midterm_ev["grade_version"] == 1
