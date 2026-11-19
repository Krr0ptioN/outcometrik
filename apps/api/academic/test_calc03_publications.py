import datetime as dt
from decimal import Decimal
from unittest.mock import patch

import pytest
from access.models import AuditEvent, Role, RoleAssignment, Scope
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from academic.controllers.publications import PublicationController
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
    academic_service_provider,
)


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _enroll(offering, student, actor, *, attempt_number: int = 1) -> Enrollment:
    RoleAssignment.objects.get_or_create(
        user=student,
        role=Role.objects.get(pk="student"),
        scope=Scope.objects.get(pk=offering.pk),
    )
    return EnrollmentService().create(
        offering=offering,
        student=student,
        attempt_number=attempt_number,
        actor=actor,
    )


@pytest.fixture
def pub_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("calc03_admin")
    coord = user_model.objects.create_user("calc03_coord")
    other_coord = user_model.objects.create_user("calc03_other_coord")
    teacher = user_model.objects.create_user("calc03_teacher")
    student1 = user_model.objects.create_user("calc03_student1")
    student2 = user_model.objects.create_user("calc03_student2")
    outsider = user_model.objects.create_user("calc03_outsider")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="CALC03 University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="PUBU", name="CALC03 University")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    term_fall = AcademicTerm.objects.create(
        institution=inst,
        year=2025,
        season="fall",
        starts_at="2025-09-01",
        ends_at="2026-01-15",
    )

    course1 = Course.objects.create(
        home_department=dept, code="CSE401", title="Software Engineering", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CSE-BS",
        title="B.S. in Computer Engineering",
        status=Program.Status.ACTIVE,
    )
    other_program = Program.objects.create(
        department=dept,
        code="EEE-BS",
        title="B.S. in Electrical Engineering",
        status=Program.Status.ACTIVE,
    )

    ProgramCourse.objects.create(
        program=program,
        course=course1,
        effective_from="2025-01-01",
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

    for idx, stu in enumerate((student1, student2, outsider), start=1):
        ProgramMembership.objects.create(
            program=program,
            user=stu,
            student_number=f"2025030{idx}",
            admitted_term=term_fall,
            status=ProgramMembership.Status.ACTIVE,
        )

    po_set = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="CALC03 Accreditation Spec",
    )
    po1 = ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO-1",
        label="Engineering Fundamentals",
        description="Apply core engineering fundamentals.",
        source_url="https://example.edu/po-1",
        ordering=1,
    )
    po2 = ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO-2",
        label="System Design",
        description="Design reliable software systems.",
        source_url="https://example.edu/po-2",
        ordering=2,
    )
    po_set.status = ProgramOutcomeSet.Status.ACTIVE
    po_set.effective_date = dt.date(2025, 1, 1)
    po_set.activated_by = coord
    po_set.activated_at = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    po_set.save()

    offering = CourseOffering.objects.create(
        program=program, course=course1, term=term_fall, section="A"
    )
    InstructorAssignmentService().create(
        offering=offering, user=teacher, assignment_role="instructor", actor=admin
    )

    # Create and approve syllabus v1 with LO-1, HW1 (required), mapping, and course PO contribution.
    syl_svc = SyllabusService()
    syllabus = syl_svc.create(offering=offering)
    lo1 = syl_svc.add_learning_outcome(
        syllabus=syllabus, code="LO-1", description="Design modular systems", order=1
    )
    sa_hw1 = syl_svc.add_assessment(
        syllabus=syllabus,
        code="HW1",
        kind=SyllabusAssessment.Kind.HOMEWORK,
        order=1,
        max_points=Decimal("100.00"),
        is_required=True,
        is_active=True,
    )
    syllabus = syl_svc.replace_assessment_lo_matrix(
        syllabus=syllabus,
        expected_revision=syllabus.mapping_revision,
        mappings=[
            {
                "assessment": sa_hw1.pk,
                "learning_outcome": lo1.pk,
                "weight": Decimal("100.00"),
                "is_active": True,
            }
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
                "learning_outcome": lo1.pk,
                "program_outcome": po2.pk,
                "weight": 3,
                "is_active": True,
            },
        ],
    )
    syl_svc.set_po_contribution(syllabus=syllabus, program_outcome=po1, weight=4)
    syl_svc.set_po_contribution(syllabus=syllabus, program_outcome=po2, weight=3)
    syllabus = syl_svc.approve(syllabus=syllabus, actor=coord)

    # Approved gradebook assessment matching HW1.
    asmt_hw1 = Assessment.objects.create(
        offering=offering,
        title="HW1",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    enr1 = _enroll(offering, student1, coord)
    enr2 = _enroll(offering, student2, coord)

    batch = GradeBatchService().create(offering=offering, name="HW1 Release")
    grade1 = GradeService().create(
        enrollment=enr1,
        assessment=asmt_hw1,
        batch=batch,
        state=Grade.State.SCORED,
        points_earned=Decimal("85.00"),
        actor=teacher,
    )
    grade2 = GradeService().create(
        enrollment=enr2,
        assessment=asmt_hw1,
        batch=batch,
        state=Grade.State.SCORED,
        points_earned=Decimal("92.00"),
        actor=teacher,
    )
    GradeBatchService().release(batch=batch, actor=coord)

    return {
        "admin": admin,
        "coord": coord,
        "other_coord": other_coord,
        "teacher": teacher,
        "student1": student1,
        "student2": student2,
        "outsider": outsider,
        "program": program,
        "other_program": other_program,
        "term": term_fall,
        "offering": offering,
        "syllabus": syllabus,
        "po_set": po_set,
        "po1": po1,
        "po2": po2,
        "lo1": lo1,
        "sa_hw1": sa_hw1,
        "asmt_hw1": asmt_hw1,
        "enr1": enr1,
        "enr2": enr2,
        "batch": batch,
        "grade1": grade1,
        "grade2": grade2,
    }


def test_di_container_resolves_publication_service():
    service = academic_service_provider.provide(PublicationService)
    assert isinstance(service, PublicationService)
    assert isinstance(service.calculation_service, CalculationService)

    class StubService:
        pass

    stub = StubService()
    ctrl = PublicationController(service=stub)
    assert ctrl.service is stub


def test_only_authorized_role_can_publish_complete_run_and_records_audit(pub_world):
    run, _ = CalculationService().run_offering(
        offering=pub_world["offering"], actor=pub_world["coord"]
    )
    assert run.status == CalculationRun.Status.COMPLETED
    assert run.is_complete_for_publication is True

    payload = {
        "run": str(run.pk),
        "expected_series_version": 0,
        "expected_input_hash": run.input_hash,
        "audience": Publication.Audience.STUDENT,
        "idempotency_key": "pub-auth-check-1",
    }

    # Instructor, student, and coordinator of another program are denied with 403.
    for denied_user in (pub_world["teacher"], pub_world["student1"], pub_world["other_coord"]):
        resp = _client(denied_user).post("/api/v1/publications/", payload, format="json")
        assert resp.status_code == 403
        assert resp["Cache-Control"] == "no-store"

    assert Publication.objects.count() == 0

    # Authorized coordinator publishes successfully -> 201 Created.
    resp = _client(pub_world["coord"]).post("/api/v1/publications/", payload, format="json")
    assert resp.status_code == 201
    assert resp["Cache-Control"] == "no-store"
    data = resp.json()
    assert data["series_version"] == 1
    assert data["audience"] == Publication.Audience.STUDENT
    assert data["input_hash"] == run.input_hash
    assert data["po_set_version"] == 1
    assert data["stale"] is False
    assert data["published_by"] == pub_world["coord"].pk

    # AuditEvent is recorded with action="outcomes.published".
    audit = AuditEvent.objects.filter(action="outcomes.published").get()
    assert audit.actor == pub_world["coord"]
    assert audit.scope_id == pub_world["offering"].pk
    assert audit.metadata["publication_id"] == data["id"]
    assert audit.metadata["series_version"] == 1
    assert audit.metadata["audience"] == Publication.Audience.STUDENT

    # Administrator (institution scope) can also publish (e.g., faculty series).
    admin_payload = {
        "run": str(run.pk),
        "expected_series_version": 0,
        "expected_input_hash": run.input_hash,
        "audience": Publication.Audience.FACULTY,
        "idempotency_key": "pub-admin-faculty-1",
    }
    resp_admin = _client(pub_world["admin"]).post(
        "/api/v1/publications/", admin_payload, format="json"
    )
    assert resp_admin.status_code == 201
    assert resp_admin.json()["series_version"] == 1
    assert resp_admin.json()["audience"] == Publication.Audience.FACULTY


def test_incomplete_run_returns_409_and_inserts_no_publication(pub_world):
    # Add an unreleased grade on a second required assessment by creating an unreleased batch
    # or marking an existing grade missing.
    GradeService().correct(
        grade=pub_world["grade2"],
        state=Grade.State.MISSING,
        points_earned=None,
        expected_version=pub_world["grade2"].version,
        reason="Reset for incomplete check",
        actor=pub_world["teacher"],
    )

    incomplete_run, _ = CalculationService().run_offering(
        offering=pub_world["offering"], actor=pub_world["coord"]
    )
    assert incomplete_run.status == CalculationRun.Status.COMPLETED
    assert incomplete_run.is_complete_for_publication is False

    resp = _client(pub_world["coord"]).post(
        "/api/v1/publications/",
        {
            "run": str(incomplete_run.pk),
            "expected_series_version": 0,
            "expected_input_hash": incomplete_run.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-incomplete-1",
        },
        format="json",
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "incomplete_run"
    assert Publication.objects.count() == 0


def test_stale_detection_across_grade_mapping_roster_and_eligibility_changes(pub_world):
    calc_svc = CalculationService()
    coord_client = _client(pub_world["coord"])

    # 1. Publish v1 from complete run.
    run1, _ = calc_svc.run_offering(offering=pub_world["offering"], actor=pub_world["coord"])
    resp1 = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(run1.pk),
            "expected_series_version": 0,
            "expected_input_hash": run1.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-v1",
        },
        format="json",
    )
    assert resp1.status_code == 201
    pub1_id = resp1.json()["id"]
    assert resp1.json()["stale"] is False

    # --- Change A: Grade correction flips stale=True without mutating publication ---
    GradeService().correct(
        grade=pub_world["grade1"],
        state=Grade.State.SCORED,
        points_earned=Decimal("90.00"),
        expected_version=pub_world["grade1"].version,
        reason="Regrade",
        actor=pub_world["teacher"],
    )
    pub1_after_grade = coord_client.get(f"/api/v1/publications/{pub1_id}/")
    assert pub1_after_grade.status_code == 200
    assert pub1_after_grade.json()["stale"] is True
    assert pub1_after_grade.json()["input_hash"] == run1.input_hash  # immutable!

    # Attempting to publish stale run1 again as v2 returns 409 and leaves v1 readable.
    stale_attempt = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(run1.pk),
            "expected_series_version": 1,
            "expected_input_hash": run1.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-stale-attempt",
        },
        format="json",
    )
    assert stale_attempt.status_code == 409
    assert stale_attempt.json()["code"] == "stale_input_hash"
    assert Publication.objects.count() == 1
    assert coord_client.get(f"/api/v1/publications/{pub1_id}/scores/").status_code == 200

    # Recalculate and publish v2 -> v2 is fresh, v1 stays stale.
    run2, _ = calc_svc.run_offering(offering=pub_world["offering"], actor=pub_world["coord"])
    resp2 = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(run2.pk),
            "expected_series_version": 1,
            "expected_input_hash": run2.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-v2",
        },
        format="json",
    )
    assert resp2.status_code == 201
    pub2_id = resp2.json()["id"]
    assert resp2.json()["series_version"] == 2
    assert resp2.json()["stale"] is False

    # --- Change B: Mapping change (approved syllabus revision) flips v2 stale=True ---
    syl_svc = SyllabusService()
    rev = syl_svc.revise(syllabus=pub_world["syllabus"])
    rev_lo = rev.learning_outcomes.get(code="LO-1")
    rev = syl_svc.replace_lo_po_matrix(
        syllabus=rev,
        expected_revision=rev.mapping_revision,
        mappings=[
            {
                "learning_outcome": rev_lo.pk,
                "program_outcome": pub_world["po1"].pk,
                "weight": 5,
                "is_active": True,
            },
            {
                "learning_outcome": rev_lo.pk,
                "program_outcome": pub_world["po2"].pk,
                "weight": 2,
                "is_active": True,
            },
        ],
    )
    syl_svc.approve(syllabus=rev, actor=pub_world["coord"])

    assert coord_client.get(f"/api/v1/publications/{pub2_id}/").json()["stale"] is True

    # Recalculate and publish v3 -> fresh.
    run3, _ = calc_svc.run_offering(offering=pub_world["offering"], actor=pub_world["coord"])
    resp3 = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(run3.pk),
            "expected_series_version": 2,
            "expected_input_hash": run3.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-v3",
        },
        format="json",
    )
    assert resp3.status_code == 201
    pub3_id = resp3.json()["id"]
    assert resp3.json()["stale"] is False

    # --- Change C: Roster change (new enrollment) flips v3 stale=True ---
    enr3 = _enroll(pub_world["offering"], pub_world["outsider"], pub_world["coord"])
    assert coord_client.get(f"/api/v1/publications/{pub3_id}/").json()["stale"] is True

    # Grade outsider & release so we can publish v4.
    GradeService().create(
        enrollment=enr3,
        assessment=pub_world["asmt_hw1"],
        batch=pub_world["batch"],
        state=Grade.State.SCORED,
        points_earned=Decimal("75.00"),
        reason="Late enrollment grade",
        actor=pub_world["teacher"],
    )
    run4, _ = calc_svc.run_offering(offering=pub_world["offering"], actor=pub_world["coord"])
    resp4 = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(run4.pk),
            "expected_series_version": 3,
            "expected_input_hash": run4.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-v4",
        },
        format="json",
    )
    assert resp4.status_code == 201
    pub4_id = resp4.json()["id"]
    assert resp4.json()["stale"] is False

    # --- Change D: Eligibility change (withdrawn enrollment) flips v4 stale=True ---
    EnrollmentService().update_status(
        enrollment=enr3,
        status=Enrollment.Status.WITHDRAWN,
        reason="Late withdrawal",
        actor=pub_world["coord"],
    )
    assert coord_client.get(f"/api/v1/publications/{pub4_id}/").json()["stale"] is True

    # Failed recalculation leaves existing publication readable.
    with (
        patch(
            "academic.services.calculations._compute_from_manifest",
            side_effect=RuntimeError("boom"),
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        calc_svc.run_offering(offering=pub_world["offering"], actor=pub_world["coord"])

    still_readable = coord_client.get(f"/api/v1/publications/{pub4_id}/")
    assert still_readable.status_code == 200
    assert still_readable.json()["series_version"] == 4
    scores_resp = coord_client.get(f"/api/v1/publications/{pub4_id}/scores/")
    assert scores_resp.status_code == 200
    assert len(scores_resp.json()) > 0


def test_series_version_conflict_and_idempotency_replay_and_conflict(pub_world):
    run, _ = CalculationService().run_offering(
        offering=pub_world["offering"], actor=pub_world["coord"]
    )
    coord_client = _client(pub_world["coord"])

    # Wrong initial expected_series_version (1 instead of 0) -> 409 series_version_conflict.
    bad_ver = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(run.pk),
            "expected_series_version": 1,
            "expected_input_hash": run.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-bad-ver",
        },
        format="json",
    )
    assert bad_ver.status_code == 409
    assert bad_ver.json()["code"] == "series_version_conflict"
    assert Publication.objects.count() == 0

    # Publish v1 -> 201 Created.
    payload = {
        "run": str(run.pk),
        "expected_series_version": 0,
        "expected_input_hash": run.input_hash,
        "audience": Publication.Audience.STUDENT,
        "idempotency_key": "pub-idem-key-1",
    }
    first = coord_client.post("/api/v1/publications/", payload, format="json")
    assert first.status_code == 201
    assert first.json()["series_version"] == 1

    # Idempotent retry with same key & payload -> 200 OK with exact same publication & series_version.
    replay = coord_client.post("/api/v1/publications/", payload, format="json")
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["series_version"] == 1
    assert Publication.objects.count() == 1
    assert AuditEvent.objects.filter(action="outcomes.published").count() == 1

    # Concurrent attempt with stale expected_series_version=0 and new key -> 409 series_version_conflict.
    concurrent = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(run.pk),
            "expected_series_version": 0,
            "expected_input_hash": run.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-concurrent-key",
        },
        format="json",
    )
    assert concurrent.status_code == 409
    assert concurrent.json()["code"] == "series_version_conflict"

    # Reusing idempotency key with different payload -> 409 idempotency_conflict.
    idem_conflict = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(run.pk),
            "expected_series_version": 1,
            "expected_input_hash": "0" * 64,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-idem-key-1",
        },
        format="json",
    )
    assert idem_conflict.status_code == 409
    assert idem_conflict.json()["code"] == "idempotency_conflict"


def test_student_visibility_only_student_audience_and_own_scores_never_drafts(pub_world):
    calc_svc = CalculationService()
    coord_client = _client(pub_world["coord"])
    stu1_client = _client(pub_world["student1"])
    outsider_client = _client(pub_world["outsider"])

    # Run offering & program calculations.
    off_run, _ = calc_svc.run_offering(offering=pub_world["offering"], actor=pub_world["coord"])
    prog_run, _ = calc_svc.run_program(program=pub_world["program"], actor=pub_world["coord"])

    # Students cannot see raw calculation runs (drafts / unpublished).
    assert stu1_client.get("/api/v1/calculation-runs/").json()["results"] == []
    assert stu1_client.get(f"/api/v1/calculation-runs/{off_run.pk}/").status_code == 404

    # Publish a faculty-only offering publication.
    fac_resp = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(off_run.pk),
            "expected_series_version": 0,
            "expected_input_hash": off_run.input_hash,
            "audience": Publication.Audience.FACULTY,
            "idempotency_key": "pub-faculty-only",
        },
        format="json",
    )
    assert fac_resp.status_code == 201
    fac_id = fac_resp.json()["id"]

    # Student CANNOT see faculty-only publication or its scores.
    assert stu1_client.get("/api/v1/publications/").json()["results"] == []
    assert stu1_client.get(f"/api/v1/publications/{fac_id}/").status_code == 404
    assert stu1_client.get(f"/api/v1/publications/{fac_id}/scores/").status_code == 404

    # Publish student-audience offering & program publications.
    stu_off_resp = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(off_run.pk),
            "expected_series_version": 0,
            "expected_input_hash": off_run.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-student-offering",
        },
        format="json",
    )
    assert stu_off_resp.status_code == 201
    stu_off_id = stu_off_resp.json()["id"]

    stu_prog_resp = coord_client.post(
        "/api/v1/publications/",
        {
            "run": str(prog_run.pk),
            "expected_series_version": 0,
            "expected_input_hash": prog_run.input_hash,
            "audience": Publication.Audience.STUDENT,
            "idempotency_key": "pub-student-program",
        },
        format="json",
    )
    assert stu_prog_resp.status_code == 201
    stu_prog_id = stu_prog_resp.json()["id"]

    # Student1 sees ONLY the two student-audience publications (not faculty-only).
    stu1_list = stu1_client.get("/api/v1/publications/").json()["results"]
    assert {item["id"] for item in stu1_list} == {stu_off_id, stu_prog_id}

    # Student1 scores endpoint returns ONLY student1's own scores, even if querying student2's ID!
    off_scores = stu1_client.get(
        f"/api/v1/publications/{stu_off_id}/scores/?student={pub_world['student2'].pk}"
    )
    assert off_scores.status_code == 200
    assert len(off_scores.json()) > 0
    assert {row["student"] for row in off_scores.json()} == {pub_world["student1"].pk}

    prog_scores = stu1_client.get(f"/api/v1/publications/{stu_prog_id}/scores/")
    assert prog_scores.status_code == 200
    assert len(prog_scores.json()) == 2  # PO-1, PO-2
    assert {row["student"] for row in prog_scores.json()} == {pub_world["student1"].pk}

    # Unenrolled outsider sees zero publications and gets 404 on student publications.
    assert outsider_client.get("/api/v1/publications/").json()["results"] == []
    assert outsider_client.get(f"/api/v1/publications/{stu_off_id}/").status_code == 404
    assert outsider_client.get(f"/api/v1/publications/{stu_prog_id}/").status_code == 404

    # Coordinator sees all 3 publications and scores for both students.
    coord_list = coord_client.get("/api/v1/publications/").json()["results"]
    assert len(coord_list) == 3
    coord_scores = coord_client.get(f"/api/v1/publications/{stu_off_id}/scores/").json()
    assert {row["student"] for row in coord_scores} == {
        pub_world["student1"].pk,
        pub_world["student2"].pk,
    }


def test_publication_immutability_enforced(pub_world):
    run, _ = CalculationService().run_offering(
        offering=pub_world["offering"], actor=pub_world["coord"]
    )
    pub, replayed = PublicationService().publish(
        actor=pub_world["coord"],
        run=run,
        expected_series_version=0,
        expected_input_hash=run.input_hash,
        audience=Publication.Audience.STUDENT,
        idempotency_key="pub-immutable-1",
    )
    assert replayed is False

    pub.series_version = 99
    with pytest.raises(ValidationError, match="immutable"):
        pub.save()

    with pytest.raises(ValidationError):
        Publication.objects.filter(pk=pub.pk).update(series_version=99)

    with pytest.raises(ProtectedError):
        pub.delete()
