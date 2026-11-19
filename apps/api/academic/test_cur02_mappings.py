import datetime as dt
from decimal import Decimal

import pytest
from access.models import Role, RoleAssignment, Scope
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from academic.models import (
    AcademicTerm,
    AssessmentLOMapping,
    Course,
    CourseOffering,
    Department,
    Institution,
    LOPOMapping,
    Program,
    ProgramCourse,
    ProgramOutcome,
    ProgramOutcomeSet,
    SyllabusAssessment,
)
from academic.services.offerings import InstructorAssignmentService
from academic.services.syllabi import SyllabusService
from academic.services.syllabus_validation import SyllabusMappingVersionConflict


@pytest.fixture
def cur02_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("cur02_admin")
    guest = user_model.objects.create_user("cur02_guest")
    teacher = user_model.objects.create_user("cur02_teacher")
    other_teacher = user_model.objects.create_user("cur02_other_teacher")
    coord = user_model.objects.create_user("cur02_coord")
    student = user_model.objects.create_user("cur02_student")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="CUR02 University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="CURU", name="CUR02 University")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CSE311", title="Software Engineering", ects=6, credits=4
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
        course=course,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2026-01-01",
    )
    ProgramCourse.objects.create(
        program=other_program,
        course=course,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2026-01-01",
    )

    po_set = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        source_reference="docs/prd-v2",
        status=ProgramOutcomeSet.Status.DRAFT,
    )
    outcomes = {}
    for idx in range(1, 12):
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
    po_set.effective_date = dt.date(2026, 1, 1)
    po_set.activated_at = dt.datetime.now(dt.UTC)
    po_set.activated_by = admin
    po_set.save()

    other_po_set = ProgramOutcomeSet.objects.create(
        program=other_program,
        version=1,
        source_reference="docs/other",
        status=ProgramOutcomeSet.Status.DRAFT,
    )
    other_po = ProgramOutcome.objects.create(
        outcome_set=other_po_set,
        code="PO1",
        label="Other PO1",
        description="Other program PO1",
        source_url="https://acibadem.edu.tr/eee",
        ordering=1,
    )
    other_po_set.status = ProgramOutcomeSet.Status.ACTIVE
    other_po_set.effective_date = dt.date(2026, 1, 1)
    other_po_set.activated_at = dt.datetime.now(dt.UTC)
    other_po_set.activated_by = admin
    other_po_set.save()

    offering = CourseOffering.objects.create(
        program=program,
        course=course,
        term=term,
        section="01",
        status=CourseOffering.Status.ACTIVE,
    )
    other_offering = CourseOffering.objects.create(
        program=program,
        course=course,
        term=term,
        section="02",
        status=CourseOffering.Status.ACTIVE,
    )

    RoleAssignment.objects.create(user=coord, scope_id=program.pk, role_id="program-coordinator")
    InstructorAssignmentService(actor=admin).create(
        offering=offering, user=teacher, assignment_role="instructor"
    )
    InstructorAssignmentService(actor=admin).create(
        offering=other_offering, user=other_teacher, assignment_role="instructor"
    )
    RoleAssignment.objects.create(user=student, scope_id=offering.pk, role_id="student")

    s_svc = SyllabusService()
    syllabus = s_svc.create(offering=offering)
    lo1 = s_svc.add_learning_outcome(
        syllabus=syllabus, code="LO1", description="Design domain models", order=1
    )
    lo2 = s_svc.add_learning_outcome(
        syllabus=syllabus, code="LO2", description="Verify and test systems", order=2
    )
    midterm = s_svc.add_assessment(
        syllabus=syllabus,
        code="MIDTERM",
        kind=SyllabusAssessment.Kind.EXAM,
        order=1,
        max_points=Decimal("100.00"),
    )
    project = s_svc.add_assessment(
        syllabus=syllabus,
        code="PROJECT",
        kind=SyllabusAssessment.Kind.PROJECT,
        order=2,
        max_points=Decimal("100.00"),
    )

    return {
        "admin": admin,
        "guest": guest,
        "teacher": teacher,
        "other_teacher": other_teacher,
        "coord": coord,
        "student": student,
        "program": program,
        "other_program": other_program,
        "po_set": po_set,
        "outcomes": outcomes,
        "other_po": other_po,
        "offering": offering,
        "other_offering": other_offering,
        "syllabus": syllabus,
        "lo1": lo1,
        "lo2": lo2,
        "midterm": midterm,
        "project": project,
    }


def test_prd_reference_60_40_and_40_100_a_lo_weights_and_2_1_lo_po_ratio(cur02_world):
    """AC1: PRD 60/40 and 40/100 A->LO weights and 2:1 LO->PO ratio enter, validate, approve, and clone."""
    client = APIClient()
    client.force_authenticate(cur02_world["teacher"])

    syllabus = cur02_world["syllabus"]
    lo1 = cur02_world["lo1"]
    lo2 = cur02_world["lo2"]
    midterm = cur02_world["midterm"]
    project = cur02_world["project"]
    po1 = cur02_world["outcomes"]["PO1"]
    po2 = cur02_world["outcomes"]["PO2"]

    # Configure A->LO matrix: LO1 gets 60/40 (sum 100), LO2 gets 40/100 (sum 140)
    res_a_lo = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {"assessment": str(midterm.pk), "learning_outcome": str(lo1.pk), "weight": "60.00"},
                {"assessment": str(project.pk), "learning_outcome": str(lo1.pk), "weight": "40.00"},
                {"assessment": str(midterm.pk), "learning_outcome": str(lo2.pk), "weight": "40.00"},
                {
                    "assessment": str(project.pk),
                    "learning_outcome": str(lo2.pk),
                    "weight": "100.00",
                },
            ],
        },
        format="json",
    )
    assert res_a_lo.status_code == 200
    assert res_a_lo.data["mapping_revision"] == 2
    assert len(res_a_lo.data["assessment_lo_mappings"]) == 4

    # Configure LO->PO matrix: LO1->PO1 weight 2, LO2->PO1 weight 1 (2:1 ratio), LO2->PO2 weight 1
    res_lo_po = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 2,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po1.pk), "weight": 2},
                {"learning_outcome": str(lo2.pk), "program_outcome": str(po1.pk), "weight": 1},
                {"learning_outcome": str(lo2.pk), "program_outcome": str(po2.pk), "weight": 1},
            ],
        },
        format="json",
    )
    assert res_lo_po.status_code == 200
    assert res_lo_po.data["mapping_revision"] == 3
    assert len(res_lo_po.data["lo_po_mappings"]) == 3

    # Validate mappings via diagnostic endpoint
    res_val = client.get(f"/api/v1/syllabi/{syllabus.pk}/mapping-validation/")
    assert res_val.status_code == 200
    report = res_val.data
    assert report["is_valid_for_approval"] is True
    assert report["errors"] == []
    assert report["unmapped_learning_outcomes"] == []
    assert report["orphaned_learning_outcomes"] == []
    assert report["unreachable_program_outcomes"] == []

    lo_by_code = {item["code"]: item for item in report["lo_statuses"]}
    assert lo_by_code["LO1"]["status"] == "MAPPED"
    assert lo_by_code["LO1"]["total_assessment_weight"] == "100.00"
    assert lo_by_code["LO2"]["status"] == "MAPPED"
    assert lo_by_code["LO2"]["total_assessment_weight"] == "140.00"

    po_by_code = {item["code"]: item for item in report["po_statuses"]}
    assert po_by_code["PO1"]["status"] == "ASSESSED"
    assert po_by_code["PO1"]["total_lo_weight"] == 3
    assert po_by_code["PO2"]["status"] == "ASSESSED"
    assert po_by_code["PO2"]["total_lo_weight"] == 1
    assert po_by_code["PO3"]["status"] == "NOT_ASSESSED"

    # Coordinator approves syllabus
    client.force_authenticate(cur02_world["coord"])
    res_approve = client.post(f"/api/v1/syllabi/{syllabus.pk}/approve/")
    assert res_approve.status_code == 200
    assert res_approve.data["status"] == "approved"

    # Instructor revises syllabus and verifies both mapping matrices are cloned into v2
    client.force_authenticate(cur02_world["teacher"])
    res_rev = client.post(f"/api/v1/syllabi/{syllabus.pk}/revise/")
    assert res_rev.status_code == 201
    rev_data = res_rev.data
    assert rev_data["version"] == 2
    assert len(rev_data["assessment_lo_mappings"]) == 4
    assert len(rev_data["lo_po_mappings"]) == 3


def test_weight_rules_non_100_sums_accepted_and_invalid_weights_rejected(cur02_world):
    """AC2: Non-100 sums accepted; negative A->LO and negative/out-of-range/decimal LO->PO rejected."""
    client = APIClient()
    client.force_authenticate(cur02_world["teacher"])

    syllabus = cur02_world["syllabus"]
    lo1 = cur02_world["lo1"]
    lo2 = cur02_world["lo2"]
    midterm = cur02_world["midterm"]
    po1 = cur02_world["outcomes"]["PO1"]

    # Non-100 sum (e.g. 25) and 0 weight (retained as inactive) are accepted
    res_ok = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {"assessment": str(midterm.pk), "learning_outcome": str(lo1.pk), "weight": "25.00"},
                {"assessment": str(midterm.pk), "learning_outcome": str(lo2.pk), "weight": "0.00"},
            ],
        },
        format="json",
    )
    assert res_ok.status_code == 200
    zero_row = AssessmentLOMapping.objects.get(syllabus=syllabus, learning_outcome=lo2)
    assert zero_row.weight == Decimal("0.00")
    assert zero_row.is_active is False

    # Negative A->LO weight (-5) is rejected with 400
    res_neg_a = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 2,
            "mappings": [
                {"assessment": str(midterm.pk), "learning_outcome": str(lo1.pk), "weight": "-5.00"},
            ],
        },
        format="json",
    )
    assert res_neg_a.status_code == 400

    # LO->PO weights 1..5 and 0 (as inactive) are accepted
    res_lopo_ok = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 2,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po1.pk), "weight": 5},
                {"learning_outcome": str(lo2.pk), "program_outcome": str(po1.pk), "weight": 0},
            ],
        },
        format="json",
    )
    assert res_lopo_ok.status_code == 200
    zero_lopo = LOPOMapping.objects.get(syllabus=syllabus, learning_outcome=lo2)
    assert zero_lopo.weight == 0
    assert zero_lopo.is_active is False

    # Negative LO->PO weight (-1) rejected
    res_lopo_neg = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 3,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po1.pk), "weight": -1},
            ],
        },
        format="json",
    )
    assert res_lopo_neg.status_code == 400

    # Out-of-range LO->PO weight (6) rejected
    res_lopo_high = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 3,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po1.pk), "weight": 6},
            ],
        },
        format="json",
    )
    assert res_lopo_high.status_code == 400

    # Decimal LO->PO weight (2.5) rejected
    res_lopo_dec = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 3,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po1.pk), "weight": 2.5},
            ],
        },
        format="json",
    )
    assert res_lopo_dec.status_code == 400


def test_cross_syllabus_and_cross_po_set_mappings_rejected(cur02_world):
    """AC3: Cross-syllabus and cross-PO-set mappings cannot be saved."""
    s_svc = SyllabusService()
    other_syllabus = s_svc.create(offering=cur02_world["other_offering"])
    other_lo = s_svc.add_learning_outcome(
        syllabus=other_syllabus, code="LO1", description="Other syllabus LO", order=1
    )
    other_asmt = s_svc.add_assessment(
        syllabus=other_syllabus,
        code="EXAM",
        kind=SyllabusAssessment.Kind.EXAM,
        order=1,
        max_points=Decimal("100.00"),
    )

    # Create a v2 draft PO set on the same program
    po_set_v2 = ProgramOutcomeSet.objects.create(
        program=cur02_world["program"],
        version=2,
        source_reference="docs/v2",
        status=ProgramOutcomeSet.Status.DRAFT,
    )
    po_v2 = ProgramOutcome.objects.create(
        outcome_set=po_set_v2,
        code="PO1",
        label="V2 PO1",
        description="V2 desc",
        source_url="https://acibadem.edu.tr/po-v2",
        ordering=1,
    )

    client = APIClient()
    client.force_authenticate(cur02_world["teacher"])
    syllabus = cur02_world["syllabus"]
    lo1 = cur02_world["lo1"]
    midterm = cur02_world["midterm"]

    # Cross-syllabus assessment in A->LO rejected
    res_cross_asmt = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {
                    "assessment": str(other_asmt.pk),
                    "learning_outcome": str(lo1.pk),
                    "weight": "50.00",
                }
            ],
        },
        format="json",
    )
    assert res_cross_asmt.status_code == 400

    # Cross-syllabus LO in A->LO rejected
    res_cross_lo = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {
                    "assessment": str(midterm.pk),
                    "learning_outcome": str(other_lo.pk),
                    "weight": "50.00",
                }
            ],
        },
        format="json",
    )
    assert res_cross_lo.status_code == 400

    # Cross-program PO in LO->PO rejected
    res_cross_prog_po = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {
                    "learning_outcome": str(lo1.pk),
                    "program_outcome": str(cur02_world["other_po"].pk),
                    "weight": 3,
                }
            ],
        },
        format="json",
    )
    assert res_cross_prog_po.status_code == 400

    # Different PO-set version PO in LO->PO rejected
    res_wrong_ver_po = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po_v2.pk), "weight": 3}
            ],
        },
        format="json",
    )
    assert res_wrong_ver_po.status_code == 400


def test_optimistic_concurrency_returns_409_conflict_on_stale_revision(cur02_world):
    """AC4: Concurrent edits cannot silently overwrite one another (409 Conflict)."""
    client = APIClient()
    client.force_authenticate(cur02_world["teacher"])

    syllabus = cur02_world["syllabus"]
    lo1 = cur02_world["lo1"]
    midterm = cur02_world["midterm"]
    po1 = cur02_world["outcomes"]["PO1"]

    # First matrix save succeeds and bumps mapping_revision from 1 -> 2
    res1 = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {"assessment": str(midterm.pk), "learning_outcome": str(lo1.pk), "weight": "60.00"}
            ],
        },
        format="json",
    )
    assert res1.status_code == 200
    assert res1.data["mapping_revision"] == 2

    # Stale A->LO save with expected_revision=1 returns 409 Conflict and preserves existing row
    res_conflict_a = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {"assessment": str(midterm.pk), "learning_outcome": str(lo1.pk), "weight": "10.00"}
            ],
        },
        format="json",
    )
    assert res_conflict_a.status_code == 409
    assert res_conflict_a.data["code"] == "version_conflict"
    assert res_conflict_a.data["current_revision"] == 2
    assert AssessmentLOMapping.objects.get(
        syllabus=syllabus, learning_outcome=lo1
    ).weight == Decimal("60.00")

    # Stale LO->PO save with expected_revision=1 also returns 409 Conflict
    res_conflict_p = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po1.pk), "weight": 4}
            ],
        },
        format="json",
    )
    assert res_conflict_p.status_code == 409
    assert res_conflict_p.data["code"] == "version_conflict"
    assert res_conflict_p.data["current_revision"] == 2

    # Service-level exception test
    s_svc = SyllabusService()
    with pytest.raises(SyllabusMappingVersionConflict) as exc_info:
        s_svc.replace_lo_po_matrix(syllabus=syllabus, expected_revision=1, mappings=[])
    assert exc_info.value.current_revision == 2


def test_unmapped_and_not_assessed_semantics_and_pre_approval_validation(cur02_world):
    """AC5: UNMAPPED LOs, NOT_ASSESSED sparse POs, orphaned LOs, and unreachable POs block approval."""
    client = APIClient()
    client.force_authenticate(cur02_world["teacher"])

    syllabus = cur02_world["syllabus"]
    lo1 = cur02_world["lo1"]
    lo2 = cur02_world["lo2"]
    midterm = cur02_world["midterm"]
    po1 = cur02_world["outcomes"]["PO1"]
    po2 = cur02_world["outcomes"]["PO2"]

    # Map Midterm -> LO1 (weight 50), leave LO2 with weight 0 (UNMAPPED)
    res_a = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {"assessment": str(midterm.pk), "learning_outcome": str(lo1.pk), "weight": "50.00"},
                {"assessment": str(midterm.pk), "learning_outcome": str(lo2.pk), "weight": "0.00"},
            ],
        },
        format="json",
    )
    assert res_a.status_code == 200

    # Map LO1 -> PO1 (weight 3), and map unmapped LO2 -> PO2 (weight 4, making PO2 unreachable!)
    res_p = client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 2,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po1.pk), "weight": 3},
                {"learning_outcome": str(lo2.pk), "program_outcome": str(po2.pk), "weight": 4},
            ],
        },
        format="json",
    )
    assert res_p.status_code == 200

    # Diagnostic endpoint reports LO2 as UNMAPPED & orphaned, and PO2 as NOT_ASSESSED & unreachable
    res_diag = client.get(f"/api/v1/syllabi/{syllabus.pk}/mapping-validation/")
    assert res_diag.status_code == 200
    diag = res_diag.data
    assert diag["is_valid_for_approval"] is False
    assert "LO2" in diag["unmapped_learning_outcomes"]
    assert "LO2" in diag["orphaned_learning_outcomes"]
    assert "PO2" in diag["unreachable_program_outcomes"]

    lo_statuses = {item["code"]: item["status"] for item in diag["lo_statuses"]}
    assert lo_statuses["LO1"] == "MAPPED"
    assert lo_statuses["LO2"] == "UNMAPPED"

    po_statuses = {item["code"]: item["status"] for item in diag["po_statuses"]}
    assert po_statuses["PO1"] == "ASSESSED"
    assert po_statuses["PO2"] == "NOT_ASSESSED"
    assert po_statuses["PO3"] == "NOT_ASSESSED"

    # Approval is blocked with 400 when unmapped/orphaned LOs or unreachable POs exist
    client.force_authenticate(cur02_world["coord"])
    res_approve_blocked = client.post(f"/api/v1/syllabi/{syllabus.pk}/approve/")
    assert res_approve_blocked.status_code == 400


def test_authorization_scope_enforcement_on_mapping_endpoints(cur02_world):
    """AC6: Unauthorized users or instructors from other offerings receive 403/404."""
    client = APIClient()
    syllabus = cur02_world["syllabus"]
    lo1 = cur02_world["lo1"]
    midterm = cur02_world["midterm"]
    po1 = cur02_world["outcomes"]["PO1"]

    # Guest receives 403/404
    client.force_authenticate(cur02_world["guest"])
    assert client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {
                    "assessment": str(midterm.pk),
                    "learning_outcome": str(lo1.pk),
                    "weight": "50.00",
                }
            ],
        },
        format="json",
    ).status_code in (403, 404)

    # Instructor assigned to another offering cannot mutate or read this offering's draft mappings
    client.force_authenticate(cur02_world["other_teacher"])
    assert client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {
                    "assessment": str(midterm.pk),
                    "learning_outcome": str(lo1.pk),
                    "weight": "50.00",
                }
            ],
        },
        format="json",
    ).status_code in (403, 404)
    assert client.post(
        f"/api/v1/syllabi/{syllabus.pk}/lo-po-mappings/",
        {
            "expected_revision": 1,
            "mappings": [
                {"learning_outcome": str(lo1.pk), "program_outcome": str(po1.pk), "weight": 3}
            ],
        },
        format="json",
    ).status_code in (403, 404)
    assert client.get(f"/api/v1/syllabi/{syllabus.pk}/mapping-validation/").status_code in (
        403,
        404,
    )

    # Student cannot mutate mappings
    client.force_authenticate(cur02_world["student"])
    assert client.post(
        f"/api/v1/syllabi/{syllabus.pk}/assessment-lo-mappings/",
        {"expected_revision": 1, "mappings": []},
        format="json",
    ).status_code in (403, 404)
