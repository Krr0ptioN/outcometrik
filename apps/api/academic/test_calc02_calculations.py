import datetime as dt
from decimal import Decimal
from unittest.mock import patch

import pytest
from access.models import Role, RoleAssignment, Scope
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from academic.controllers.calculations import CalculationRunController
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
    SyllabusAssessment,
)
from academic.services import (
    CALC_POLICY_VERSION,
    ENGINE_VERSION,
    CalculationService,
    EnrollmentService,
    GradeBatchService,
    GradeService,
    InstructorAssignmentService,
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
def calc_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("calc02_admin")
    coord = user_model.objects.create_user("calc02_coord")
    other_coord = user_model.objects.create_user("calc02_other_coord")
    teacher = user_model.objects.create_user("calc02_teacher")
    other_teacher = user_model.objects.create_user("calc02_other_teacher")
    student = user_model.objects.create_user("calc02_student")
    student2 = user_model.objects.create_user("calc02_student2")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="CALC02 University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="CLCU", name="CALC02 University")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    term_fall = AcademicTerm.objects.create(
        institution=inst,
        year=2025,
        season="fall",
        starts_at="2025-09-01",
        ends_at="2026-01-15",
    )
    term_spring = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="spring",
        starts_at="2026-02-01",
        ends_at="2026-06-15",
    )
    term_summer = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="summer",
        starts_at="2026-07-01",
        ends_at="2026-08-30",
    )

    course1 = Course.objects.create(
        home_department=dept, code="CSE301", title="Algorithms", ects=6, credits=4
    )
    course2 = Course.objects.create(
        home_department=dept, code="CSE302", title="Databases", ects=6, credits=4
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

    for c in (course1, course2):
        ProgramCourse.objects.create(
            program=program,
            course=c,
            status=ProgramCourse.Status.APPROVED,
            effective_from="2025-01-01",
        )
    ProgramCourse.objects.create(
        program=other_program,
        course=course1,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2025-01-01",
    )

    # Active PO-set for main program with PO1, PO2, PO3
    po_set = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        source_reference="docs/prd-v2",
        status=ProgramOutcomeSet.Status.DRAFT,
    )
    outcomes = {}
    for idx in (1, 2, 3):
        code = f"PO{idx}"
        outcomes[code] = ProgramOutcome.objects.create(
            outcome_set=po_set,
            code=code,
            label=f"Program Outcome {idx}",
            description=f"Description for {code}",
            source_url="https://acibadem.edu.tr/po",
            ordering=idx,
        )
    po_set.status = ProgramOutcomeSet.Status.ACTIVE
    po_set.effective_date = dt.date(2025, 1, 1)
    po_set.activated_at = dt.datetime.now(dt.UTC)
    po_set.activated_by = admin
    po_set.save()

    # Active PO-set for other_program
    other_po_set = ProgramOutcomeSet.objects.create(
        program=other_program,
        version=1,
        source_reference="docs/prd-v2",
        status=ProgramOutcomeSet.Status.DRAFT,
    )
    ProgramOutcome.objects.create(
        outcome_set=other_po_set,
        code="PO1",
        label="Other PO1",
        description="Other",
        source_url="https://acibadem.edu.tr/po",
        ordering=1,
    )
    other_po_set.status = ProgramOutcomeSet.Status.ACTIVE
    other_po_set.effective_date = dt.date(2025, 1, 1)
    other_po_set.activated_at = dt.datetime.now(dt.UTC)
    other_po_set.activated_by = admin
    other_po_set.save()

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

    ProgramMembership.objects.create(
        program=program,
        user=student,
        student_number="20250001",
        admitted_term=term_fall,
        status=ProgramMembership.Status.ACTIVE,
    )
    ProgramMembership.objects.create(
        program=program,
        user=student2,
        student_number="20250002",
        admitted_term=term_fall,
        status=ProgramMembership.Status.ACTIVE,
    )

    offering1 = CourseOffering.objects.create(
        program=program, course=course1, term=term_fall, section="01"
    )
    other_offering = CourseOffering.objects.create(
        program=other_program, course=course1, term=term_fall, section="01"
    )

    InstructorAssignmentService(actor=admin).create(
        offering=offering1, user=teacher, assignment_role="instructor"
    )
    InstructorAssignmentService(actor=admin).create(
        offering=other_offering, user=other_teacher, assignment_role="instructor"
    )

    return {
        "admin": admin,
        "coord": coord,
        "other_coord": other_coord,
        "teacher": teacher,
        "other_teacher": other_teacher,
        "student": student,
        "student2": student2,
        "program": program,
        "other_program": other_program,
        "term_fall": term_fall,
        "term_spring": term_spring,
        "term_summer": term_summer,
        "course1": course1,
        "course2": course2,
        "offering1": offering1,
        "other_offering": other_offering,
        "po_set": po_set,
        "outcomes": outcomes,
    }


def _setup_canonical_offering(
    world, *, release_batch: bool = True, include_second_student: bool = False
):
    """Build PRD canonical offering:
    Midterm=90/100, Project=80/100
    A->LO: LO1=(Midterm:60, Project:40) -> 86.0; LO2=(Midterm:40, Project:100) -> 82.857142... (82.9)
    LO->PO: PO1=(LO1:2, LO2:1) -> 84.952380... (85.0); PO2=(LO2:1) -> 82.857142... (82.9); PO3 unassessed.
    """
    syl_svc = SyllabusService()
    grade_svc = GradeService()
    batch_svc = GradeBatchService()

    offering = world["offering1"]
    outcomes = world["outcomes"]

    syllabus = syl_svc.create(offering=offering)
    lo1 = syl_svc.add_learning_outcome(
        syllabus=syllabus, code="LO1", description="Design algorithms", order=1
    )
    lo2 = syl_svc.add_learning_outcome(
        syllabus=syllabus, code="LO2", description="Analyze complexity", order=2
    )
    sa_mid = syl_svc.add_assessment(
        syllabus=syllabus,
        code="Midterm",
        kind=SyllabusAssessment.Kind.EXAM,
        order=1,
        is_required=True,
        is_active=True,
        max_points=Decimal("100.00"),
    )
    sa_prj = syl_svc.add_assessment(
        syllabus=syllabus,
        code="Project",
        kind=SyllabusAssessment.Kind.PROJECT,
        order=2,
        is_required=True,
        is_active=True,
        max_points=Decimal("100.00"),
    )
    syllabus = syl_svc.replace_assessment_lo_matrix(
        syllabus=syllabus,
        expected_revision=syllabus.mapping_revision,
        mappings=[
            {
                "assessment": sa_mid.pk,
                "learning_outcome": lo1.pk,
                "weight": Decimal("60.00"),
                "is_active": True,
            },
            {
                "assessment": sa_prj.pk,
                "learning_outcome": lo1.pk,
                "weight": Decimal("40.00"),
                "is_active": True,
            },
            {
                "assessment": sa_mid.pk,
                "learning_outcome": lo2.pk,
                "weight": Decimal("40.00"),
                "is_active": True,
            },
            {
                "assessment": sa_prj.pk,
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
                "program_outcome": outcomes["PO1"].pk,
                "weight": 2,
                "is_active": True,
            },
            {
                "learning_outcome": lo2.pk,
                "program_outcome": outcomes["PO1"].pk,
                "weight": 1,
                "is_active": True,
            },
            {
                "learning_outcome": lo2.pk,
                "program_outcome": outcomes["PO2"].pk,
                "weight": 1,
                "is_active": True,
            },
        ],
    )
    syl_svc.set_po_contribution(syllabus=syllabus, program_outcome=outcomes["PO1"], weight=5)
    syllabus = syl_svc.approve(syllabus=syllabus, actor=world["coord"])

    a_mid = Assessment.objects.create(
        offering=offering,
        title="Midterm",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    a_prj = Assessment.objects.create(
        offering=offering,
        title="Project",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    batch = batch_svc.create(offering=offering, name="Official Release")

    enr1 = _enroll(offering, world["student"], world["coord"])
    g_mid = grade_svc.create(
        enrollment=enr1,
        assessment=a_mid,
        batch=batch,
        state=Grade.State.SCORED,
        points_earned=Decimal("90.00"),
        actor=world["teacher"],
    )
    g_prj = grade_svc.create(
        enrollment=enr1,
        assessment=a_prj,
        batch=batch,
        state=Grade.State.SCORED,
        points_earned=Decimal("80.00"),
        actor=world["teacher"],
    )

    enr2 = None
    if include_second_student:
        enr2 = _enroll(offering, world["student2"], world["coord"])

    if release_batch:
        batch = batch_svc.release(batch=batch, actor=world["teacher"])

    return {
        "syllabus": syllabus,
        "lo1": lo1,
        "lo2": lo2,
        "sa_mid": sa_mid,
        "sa_prj": sa_prj,
        "a_mid": a_mid,
        "a_prj": a_prj,
        "batch": batch,
        "enr1": enr1,
        "enr2": enr2,
        "g_mid": g_mid,
        "g_prj": g_prj,
    }


# 1. Canonical offering calculation (60/40, 40/100 A->LO and 2:1 LO->PO)
@pytest.mark.django_db
def test_canonical_offering_calculation_decimal_precision_and_evidence(calc_world):
    setup = _setup_canonical_offering(calc_world)
    client = _client(calc_world["teacher"])

    resp = client.post(
        "/api/v1/calculation-runs/offering/",
        {"offering": str(calc_world["offering1"].pk)},
        format="json",
    )
    assert resp.status_code == 201
    run_data = resp.json()
    assert run_data["scope_kind"] == "offering"
    assert run_data["status"] == "completed"
    assert run_data["is_complete_for_publication"] is True
    assert run_data["engine_version"] == ENGINE_VERSION
    assert run_data["policy_version"] == CALC_POLICY_VERSION
    assert run_data["po_set_version"] == 1
    assert len(run_data["input_hash"]) == 64

    scores_resp = client.get(f"/api/v1/calculation-runs/{run_data['id']}/scores/")
    assert scores_resp.status_code == 200
    scores = scores_resp.json()

    by_key = {(s["level"], s["outcome_code"]): s for s in scores}

    lo1 = by_key[("lo", "LO1")]
    assert lo1["status"] == "OK"
    assert Decimal(lo1["value"]) == Decimal("86.000000")
    assert lo1["display_value"] == "86.0"
    assert Decimal(lo1["numerator"]) == Decimal("8600.000000")
    assert Decimal(lo1["denominator"]) == Decimal("100.000000")
    assert Decimal(lo1["coverage"]) == Decimal("1.0000")
    assert {c["grade_id"] for c in lo1["evidence"]["contributions"]} == {
        str(setup["g_mid"].pk),
        str(setup["g_prj"].pk),
    }

    lo2 = by_key[("lo", "LO2")]
    assert lo2["status"] == "OK"
    assert Decimal(lo2["value"]) == Decimal("82.857143")
    assert lo2["display_value"] == "82.9"
    assert Decimal(lo2["numerator"]) == Decimal("11600.000000")
    assert Decimal(lo2["denominator"]) == Decimal("140.000000")

    # PO1 must use full-precision LO2 (82.857142...), NOT display-rounded 82.9!
    po1 = by_key[("course_po", "PO1")]
    assert po1["status"] == "OK"
    assert Decimal("84.952") < Decimal(po1["value"]) < Decimal("84.953")
    assert po1["display_value"] == "85.0"
    assert Decimal(po1["denominator"]) == Decimal("3.000000")
    assert Decimal(po1["coverage"]) == Decimal("1.0000")
    assert {c["lo_code"] for c in po1["evidence"]["contributions"]} == {"LO1", "LO2"}

    po2 = by_key[("course_po", "PO2")]
    assert po2["status"] == "OK"
    assert po2["display_value"] == "82.9"

    # PO3 has no LO->PO mappings -> NOT_ASSESSED, never 0
    po3 = by_key[("course_po", "PO3")]
    assert po3["status"] == "NOT_ASSESSED"
    assert po3["value"] is None
    assert po3["display_value"] is None


# 2. Canonical cumulative program calculation + latest-completed-approved-attempt policy
@pytest.mark.django_db
def test_canonical_cumulative_program_calculation_and_attempt_policy(calc_world):
    syl_svc = SyllabusService()
    enr_svc = EnrollmentService()
    grade_svc = GradeService()
    batch_svc = GradeBatchService()

    outcomes = calc_world["outcomes"]
    program = calc_world["program"]
    student = calc_world["student"]

    def _build_course_offering(
        *,
        offering: CourseOffering,
        score_points: Decimal,
        po1_weight: int,
        enr_status: str,
        attempt_number: int,
    ):
        syl = syl_svc.create(offering=offering)
        lo = syl_svc.add_learning_outcome(syllabus=syl, code="LO1", description="Core LO", order=1)
        sa = syl_svc.add_assessment(
            syllabus=syl,
            code="Final",
            kind=SyllabusAssessment.Kind.EXAM,
            order=1,
            is_required=True,
            is_active=True,
            max_points=Decimal("100.00"),
        )
        syl = syl_svc.replace_assessment_lo_matrix(
            syllabus=syl,
            expected_revision=syl.mapping_revision,
            mappings=[
                {
                    "assessment": sa.pk,
                    "learning_outcome": lo.pk,
                    "weight": Decimal("100.00"),
                    "is_active": True,
                }
            ],
        )
        syl = syl_svc.replace_lo_po_matrix(
            syllabus=syl,
            expected_revision=syl.mapping_revision,
            mappings=[
                {
                    "learning_outcome": lo.pk,
                    "program_outcome": outcomes["PO1"].pk,
                    "weight": 1,
                    "is_active": True,
                }
            ],
        )
        syl_svc.set_po_contribution(
            syllabus=syl, program_outcome=outcomes["PO1"], weight=po1_weight
        )
        syl = syl_svc.approve(syllabus=syl, actor=calc_world["coord"])

        asmt = Assessment.objects.create(
            offering=offering,
            title="Final",
            points_possible=Decimal("100.00"),
            status=Assessment.Status.APPROVED,
        )
        batch = batch_svc.create(offering=offering, name="Final Batch")
        enr = _enroll(
            offering,
            student,
            calc_world["coord"],
            attempt_number=attempt_number,
        )
        grade_svc.create(
            enrollment=enr,
            assessment=asmt,
            batch=batch,
            state=Grade.State.SCORED,
            points_earned=score_points,
            actor=calc_world["coord"],
        )
        batch_svc.release(batch=batch, actor=calc_world["coord"])
        if enr_status != Enrollment.Status.ENROLLED:
            enr_svc.update_status(
                enrollment=enr,
                status=enr_status,
                reason="term finalized",
                actor=calc_world["coord"],
            )
        return syl, enr

    # Course 1 Attempt 1 (Fall, completed, score 60) - superseded by Attempt 2
    _build_course_offering(
        offering=calc_world["offering1"],
        score_points=Decimal("60.00"),
        po1_weight=5,
        enr_status=Enrollment.Status.COMPLETED,
        attempt_number=1,
    )
    # Course 1 Attempt 2 (Spring, completed, score 85, weight 5) -> MUST BE SELECTED
    c1_retake = CourseOffering.objects.create(
        program=program, course=calc_world["course1"], term=calc_world["term_spring"], section="01"
    )
    _build_course_offering(
        offering=c1_retake,
        score_points=Decimal("85.00"),
        po1_weight=5,
        enr_status=Enrollment.Status.COMPLETED,
        attempt_number=2,
    )
    # Course 1 Attempt 3 (Summer, in-progress enrolled, score 10) -> MUST NOT override completed attempt 2
    c1_in_progress = CourseOffering.objects.create(
        program=program, course=calc_world["course1"], term=calc_world["term_summer"], section="01"
    )
    _build_course_offering(
        offering=c1_in_progress,
        score_points=Decimal("10.00"),
        po1_weight=5,
        enr_status=Enrollment.Status.ENROLLED,
        attempt_number=3,
    )

    # Course 2 Attempt 1 (Spring, completed, score 90, weight 3) -> MUST BE SELECTED
    c2_offering = CourseOffering.objects.create(
        program=program, course=calc_world["course2"], term=calc_world["term_spring"], section="01"
    )
    _build_course_offering(
        offering=c2_offering,
        score_points=Decimal("90.00"),
        po1_weight=3,
        enr_status=Enrollment.Status.COMPLETED,
        attempt_number=1,
    )

    client = _client(calc_world["coord"])
    resp = client.post(
        "/api/v1/calculation-runs/program/",
        {"program": str(program.pk)},
        format="json",
    )
    assert resp.status_code == 201
    run_data = resp.json()
    assert run_data["scope_kind"] == "program"
    assert run_data["status"] == "completed"
    assert run_data["is_complete_for_publication"] is True
    assert run_data["policy_version"] == CALC_POLICY_VERSION

    scores_resp = client.get(f"/api/v1/calculation-runs/{run_data['id']}/scores/")
    assert scores_resp.status_code == 200
    by_code = {s["outcome_code"]: s for s in scores_resp.json()}

    # (85*5 + 90*3) / (5 + 3) = 695 / 8 = 86.875 -> display "86.9"
    po1 = by_code["PO1"]
    assert po1["level"] == "cumulative_po"
    assert po1["status"] == "OK"
    assert Decimal(po1["value"]) == Decimal("86.875000")
    assert po1["display_value"] == "86.9"
    assert Decimal(po1["numerator"]) == Decimal("695.000000")
    assert Decimal(po1["denominator"]) == Decimal("8.000000")
    assert Decimal(po1["coverage"]) == Decimal("1.0000")
    chosen_offerings = {c["offering_id"] for c in po1["evidence"]["contributions"]}
    assert chosen_offerings == {str(c1_retake.pk), str(c2_offering.pk)}

    # Unassessed PO2 & PO3 must remain NOT_ASSESSED, never 0
    assert by_code["PO2"]["status"] == "NOT_ASSESSED"
    assert by_code["PO2"]["value"] is None
    assert by_code["PO3"]["status"] == "NOT_ASSESSED"
    assert by_code["PO3"]["value"] is None


# 3. Missing required grades -> INCOMPLETE status & is_complete_for_publication=False
@pytest.mark.django_db
def test_missing_required_grades_and_unreleased_batch_block_publication(calc_world):
    # Include student2 who has NO grades yet -> INCOMPLETE
    setup = _setup_canonical_offering(calc_world, release_batch=False, include_second_student=True)
    svc = CalculationService()

    run_preview, created = svc.run_offering(
        offering=calc_world["offering1"], actor=calc_world["teacher"]
    )
    assert created is True
    assert run_preview.status == CalculationRun.Status.COMPLETED
    assert run_preview.is_complete_for_publication is False

    student2_scores = OutcomeScore.objects.filter(run=run_preview, student=calc_world["student2"])
    by_key = {(s.level, s.outcome_code): s for s in student2_scores}
    assert by_key[("lo", "LO1")].status == OutcomeScore.Status.INCOMPLETE
    assert by_key[("lo", "LO1")].value is None
    assert by_key[("course_po", "PO1")].status == OutcomeScore.Status.INCOMPLETE
    assert by_key[("course_po", "PO1")].value is None

    # Fill student2's grades in the still-unreleased batch: scores are OK in preview,
    # but publication is still blocked until the batch is released.
    grade_svc = GradeService()
    grade_svc.create(
        enrollment=setup["enr2"],
        assessment=setup["a_mid"],
        batch=setup["batch"],
        state=Grade.State.SCORED,
        points_earned=Decimal("70.00"),
        actor=calc_world["teacher"],
    )
    grade_svc.create(
        enrollment=setup["enr2"],
        assessment=setup["a_prj"],
        batch=setup["batch"],
        state=Grade.State.SCORED,
        points_earned=Decimal("70.00"),
        actor=calc_world["teacher"],
    )

    run_unreleased, created2 = svc.run_offering(
        offering=calc_world["offering1"], actor=calc_world["teacher"]
    )
    assert created2 is True
    assert run_unreleased.input_hash != run_preview.input_hash
    assert run_unreleased.is_complete_for_publication is False

    # Releasing the batch creates a new hash/run and unlocks publication eligibility.
    GradeBatchService().release(batch=setup["batch"], actor=calc_world["teacher"])
    run_released, created3 = svc.run_offering(
        offering=calc_world["offering1"], actor=calc_world["teacher"]
    )
    assert created3 is True
    assert run_released.input_hash != run_unreleased.input_hash
    assert run_released.is_complete_for_publication is True


# 4. Unmapped LOs (UNMAPPED), unassessed POs (NOT_ASSESSED), and ALL_EXEMPT never become 0
@pytest.mark.django_db
def test_unmapped_not_assessed_and_all_exempt_never_become_zero(calc_world):
    syl_svc = SyllabusService()
    grade_svc = GradeService()
    batch_svc = GradeBatchService()

    offering = calc_world["offering1"]
    outcomes = calc_world["outcomes"]

    syl = syl_svc.create(offering=offering)
    lo_unmapped = syl_svc.add_learning_outcome(
        syllabus=syl, code="LO1", description="Unmapped LO", order=1
    )
    lo_exempt = syl_svc.add_learning_outcome(
        syllabus=syl, code="LO2", description="Exempt LO", order=2
    )
    sa_exam = syl_svc.add_assessment(
        syllabus=syl,
        code="Exam1",
        kind=SyllabusAssessment.Kind.EXAM,
        order=1,
        is_required=True,
        is_active=True,
        max_points=Decimal("100.00"),
    )
    # Only LO2 is mapped to Exam1; LO1 has no assessment mappings -> UNMAPPED
    syl = syl_svc.replace_assessment_lo_matrix(
        syllabus=syl,
        expected_revision=syl.mapping_revision,
        mappings=[
            {
                "assessment": sa_exam.pk,
                "learning_outcome": lo_exempt.pk,
                "weight": Decimal("100.00"),
                "is_active": True,
            }
        ],
    )
    # PO1 maps to LO2 (ALL_EXEMPT); PO2 maps to LO1 (UNMAPPED -> NOT_ASSESSED); PO3 has no mappings (NOT_ASSESSED)
    # Kept as a draft syllabus preview since approval forbids unmapped LOs.
    syl = syl_svc.replace_lo_po_matrix(
        syllabus=syl,
        expected_revision=syl.mapping_revision,
        mappings=[
            {
                "learning_outcome": lo_exempt.pk,
                "program_outcome": outcomes["PO1"].pk,
                "weight": 2,
                "is_active": True,
            },
            {
                "learning_outcome": lo_unmapped.pk,
                "program_outcome": outcomes["PO2"].pk,
                "weight": 1,
                "is_active": True,
            },
        ],
    )

    asmt = Assessment.objects.create(
        offering=offering,
        title="Exam1",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    batch = batch_svc.create(offering=offering, name="Release")
    enr = _enroll(offering, calc_world["student"], calc_world["coord"])
    grade_svc.create(
        enrollment=enr,
        assessment=asmt,
        batch=batch,
        state=Grade.State.EXEMPT,
        points_earned=None,
        reason="medical excuse",
        actor=calc_world["teacher"],
    )
    batch_svc.release(batch=batch, actor=calc_world["teacher"])

    run, _ = CalculationService().run_offering(offering=offering, actor=calc_world["teacher"])
    by_key = {(s.level, s.outcome_code): s for s in run.scores.all()}

    assert by_key[("lo", "LO1")].status == OutcomeScore.Status.UNMAPPED
    assert by_key[("lo", "LO1")].value is None
    assert by_key[("lo", "LO1")].evidence["display_value"] is None

    assert by_key[("lo", "LO2")].status == OutcomeScore.Status.ALL_EXEMPT
    assert by_key[("lo", "LO2")].value is None
    assert by_key[("lo", "LO2")].evidence["exemptions"] == [
        {"assessment_code": "Exam1", "reason": "medical excuse"}
    ]

    assert by_key[("course_po", "PO1")].status == OutcomeScore.Status.ALL_EXEMPT
    assert by_key[("course_po", "PO1")].value is None

    assert by_key[("course_po", "PO2")].status == OutcomeScore.Status.NOT_ASSESSED
    assert by_key[("course_po", "PO2")].value is None

    assert by_key[("course_po", "PO3")].status == OutcomeScore.Status.NOT_ASSESSED
    assert by_key[("course_po", "PO3")].value is None


# 5. Grade correction / roster / mapping change -> new input_hash and new run
@pytest.mark.django_db
def test_input_changes_produce_new_hash_and_new_run(calc_world):
    setup = _setup_canonical_offering(calc_world)
    svc = CalculationService()
    offering = calc_world["offering1"]

    run1, created1 = svc.run_offering(offering=offering, actor=calc_world["teacher"])
    assert created1 is True

    # (a) Grade correction changes input_hash and creates a new run
    GradeService().correct(
        grade=setup["g_mid"],
        expected_version=setup["g_mid"].version,
        state=Grade.State.SCORED,
        points_earned=Decimal("95.00"),
        reason="regrade",
        actor=calc_world["teacher"],
    )
    run2, created2 = svc.run_offering(offering=offering, actor=calc_world["teacher"])
    assert created2 is True
    assert run2.pk != run1.pk
    assert run2.input_hash != run1.input_hash

    # (b) Roster change (adding a student) changes input_hash and creates a new run
    _enroll(offering, calc_world["student2"], calc_world["coord"])
    run3, created3 = svc.run_offering(offering=offering, actor=calc_world["teacher"])
    assert created3 is True
    assert run3.pk != run2.pk
    assert run3.input_hash != run2.input_hash

    # (c) Syllabus mapping revision + approval changes input_hash and creates a new run
    syl_svc = SyllabusService()
    rev = syl_svc.revise(syllabus=setup["syllabus"])
    rev_lo1 = rev.learning_outcomes.get(code="LO1")
    rev_lo2 = rev.learning_outcomes.get(code="LO2")
    rev_mid = rev.assessments.get(code="Midterm")
    rev_prj = rev.assessments.get(code="Project")
    rev = syl_svc.replace_assessment_lo_matrix(
        syllabus=rev,
        expected_revision=rev.mapping_revision,
        mappings=[
            {
                "assessment": rev_mid.pk,
                "learning_outcome": rev_lo1.pk,
                "weight": Decimal("50.00"),
                "is_active": True,
            },
            {
                "assessment": rev_prj.pk,
                "learning_outcome": rev_lo1.pk,
                "weight": Decimal("50.00"),
                "is_active": True,
            },
            {
                "assessment": rev_mid.pk,
                "learning_outcome": rev_lo2.pk,
                "weight": Decimal("40.00"),
                "is_active": True,
            },
            {
                "assessment": rev_prj.pk,
                "learning_outcome": rev_lo2.pk,
                "weight": Decimal("100.00"),
                "is_active": True,
            },
        ],
    )
    syl_svc.approve(syllabus=rev, actor=calc_world["coord"])
    run4, created4 = svc.run_offering(offering=offering, actor=calc_world["teacher"])
    assert created4 is True
    assert run4.pk != run3.pk
    assert run4.input_hash != run3.input_hash


# 6. Idempotent retry returns the exact same completed CalculationRun.id
@pytest.mark.django_db
def test_idempotent_retry_returns_same_completed_run_and_manifest_helper_matches(calc_world):
    _setup_canonical_offering(calc_world)
    client = _client(calc_world["teacher"])
    offering = calc_world["offering1"]

    r1 = client.post(
        "/api/v1/calculation-runs/offering/",
        {"offering": str(offering.pk)},
        format="json",
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/v1/calculation-runs/offering/",
        {"offering": str(offering.pk)},
        format="json",
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"]
    assert CalculationRun.objects.filter(offering=offering).count() == 1

    # build_manifest_and_hash matches stored input_hash (for CALC-03 stale detection)
    svc = CalculationService()
    _manifest, computed_hash, po_ver = svc.build_manifest_and_hash(
        scope_kind=CalculationRun.ScopeKind.OFFERING,
        program=offering.program,
        offering=offering,
    )
    assert computed_hash == r1.json()["input_hash"]
    assert po_ver == 1


# 7. Failed run exposes zero partial OutcomeScore rows
@pytest.mark.django_db
def test_failed_run_persists_zero_scores(calc_world):
    _setup_canonical_offering(calc_world)
    svc = CalculationService()

    with (
        patch(
            "academic.services.calculations._compute_from_manifest",
            side_effect=RuntimeError("simulated kernel failure"),
        ),
        pytest.raises(RuntimeError, match="simulated kernel failure"),
    ):
        svc.run_offering(offering=calc_world["offering1"], actor=calc_world["teacher"])

    failed_run = CalculationRun.objects.get(offering=calc_world["offering1"])
    assert failed_run.status == CalculationRun.Status.FAILED
    assert failed_run.is_complete_for_publication is False
    assert "simulated kernel failure" in failed_run.error_detail
    assert OutcomeScore.objects.filter(run=failed_run).count() == 0


# 8. Scoped authorization: students and cross-program/offering users denied
@pytest.mark.django_db
def test_scoped_authorization_and_student_isolation(calc_world):
    _setup_canonical_offering(calc_world)
    offering = calc_world["offering1"]
    program = calc_world["program"]

    # Teacher creates offering run; coordinator creates program run
    teacher_client = _client(calc_world["teacher"])
    coord_client = _client(calc_world["coord"])

    off_resp = teacher_client.post(
        "/api/v1/calculation-runs/offering/",
        {"offering": str(offering.pk)},
        format="json",
    )
    assert off_resp.status_code == 201
    off_run_id = off_resp.json()["id"]

    # Teacher cannot run program-level calculation (no outcomes.view on program)
    assert (
        teacher_client.post(
            "/api/v1/calculation-runs/program/",
            {"program": str(program.pk)},
            format="json",
        ).status_code
        == 403
    )

    prog_resp = coord_client.post(
        "/api/v1/calculation-runs/program/",
        {"program": str(program.pk)},
        format="json",
    )
    assert prog_resp.status_code == 201
    prog_run_id = prog_resp.json()["id"]

    # Teacher cannot see program-level run
    assert teacher_client.get(f"/api/v1/calculation-runs/{prog_run_id}/").status_code == 404

    # Student is denied on POST, sees empty list, gets 404 on detail & scores
    student_client = _client(calc_world["student"])
    assert (
        student_client.post(
            "/api/v1/calculation-runs/offering/",
            {"offering": str(offering.pk)},
            format="json",
        ).status_code
        == 403
    )
    assert (
        student_client.post(
            "/api/v1/calculation-runs/program/",
            {"program": str(program.pk)},
            format="json",
        ).status_code
        == 403
    )
    assert student_client.get("/api/v1/calculation-runs/").json()["results"] == []
    assert student_client.get(f"/api/v1/calculation-runs/{off_run_id}/").status_code == 404
    assert student_client.get(f"/api/v1/calculation-runs/{off_run_id}/scores/").status_code == 404

    # Cross-offering teacher & cross-program coordinator are denied
    other_teacher_client = _client(calc_world["other_teacher"])
    assert (
        other_teacher_client.post(
            "/api/v1/calculation-runs/offering/",
            {"offering": str(offering.pk)},
            format="json",
        ).status_code
        == 403
    )
    assert other_teacher_client.get(f"/api/v1/calculation-runs/{off_run_id}/").status_code == 404

    other_coord_client = _client(calc_world["other_coord"])
    assert (
        other_coord_client.post(
            "/api/v1/calculation-runs/program/",
            {"program": str(program.pk)},
            format="json",
        ).status_code
        == 403
    )
    assert other_coord_client.get(f"/api/v1/calculation-runs/{prog_run_id}/").status_code == 404
    assert (
        other_coord_client.get(f"/api/v1/calculation-runs/{prog_run_id}/scores/").status_code == 404
    )


# 9. Wireup DI container & controller constructor injection
@pytest.mark.django_db
def test_calculation_service_wireup_di_and_controller_injection():
    resolved = academic_service_provider.provide(CalculationService)
    assert isinstance(resolved, CalculationService)

    custom_service = CalculationService()
    controller = CalculationRunController(service=custom_service)
    assert controller.service is custom_service
