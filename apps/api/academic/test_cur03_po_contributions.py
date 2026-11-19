import datetime as dt
from decimal import Decimal

import pytest
from access.models import RoleAssignment
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from academic import policy
from academic.models import (
    AcademicTerm,
    Course,
    CoursePOContribution,
    Department,
    Institution,
    Program,
    ProgramCourse,
    ProgramOutcome,
    ProgramOutcomeSet,
    Syllabus,
)
from academic.services import (
    CourseOfferingService,
    InstructorAssignmentService,
    ProgramOutcomeSetService,
    SyllabusService,
)

pytestmark = pytest.mark.django_db
User = get_user_model()


def grant_role(user, scope_id, role):
    return RoleAssignment.objects.get_or_create(
        user=user, scope_id=scope_id, role_id=role, revoked_at__isnull=True
    )[0]


@pytest.fixture
def cur03_world():
    inst = Institution.objects.create(code="ACU", name="Acibadem University")
    admin = User.objects.create_user("cur03_admin", password="x")
    grant_role(admin, inst.pk, "administrator")

    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    program = Program.objects.create(department=dept, code="CENG", title="Computer Engineering")
    other_program = Program.objects.create(
        department=dept, code="SENG", title="Software Engineering"
    )

    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at=dt.date(2026, 9, 1),
        ends_at=dt.date(2027, 1, 15),
    )
    course = Course.objects.create(
        home_department=dept, code="CSE311", title="Software Engineering", ects=6, credits=3
    )
    ProgramCourse.objects.create(
        program=program,
        course=course,
        effective_from=dt.date(2026, 1, 1),
        status=ProgramCourse.Status.APPROVED,
    )
    ProgramCourse.objects.create(
        program=other_program,
        course=course,
        effective_from=dt.date(2026, 1, 1),
        status=ProgramCourse.Status.APPROVED,
    )

    po_set = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="docs/PRD.md",
    )
    outcomes = {}
    for i in range(1, 4):
        outcomes[f"PO{i}"] = ProgramOutcome.objects.create(
            outcome_set=po_set,
            code=f"PO{i}",
            label=f"Outcome {i}",
            description=f"Outcome {i} description",
            source_url=f"docs/po#{i}",
            ordering=i,
        )
    po_set = ProgramOutcomeSetService(actor=admin).activate(
        instance=po_set, effective_date=dt.date(2026, 1, 1)
    )

    other_po_set = ProgramOutcomeSet.objects.create(
        program=other_program,
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="docs/other",
    )
    other_po = ProgramOutcome.objects.create(
        outcome_set=other_po_set,
        code="PO1",
        label="Other PO1",
        description="Other program outcome",
        source_url="docs/other#1",
        ordering=1,
    )
    other_po_set = ProgramOutcomeSetService(actor=admin).activate(
        instance=other_po_set, effective_date=dt.date(2026, 1, 1)
    )

    offering = CourseOfferingService(actor=admin).create(
        program=program, course=course, term=term, section="01"
    )

    coordinator = User.objects.create_user("cur03_coord", password="x")
    grant_role(coordinator, program.pk, "program-coordinator")

    other_coordinator = User.objects.create_user("cur03_other_coord", password="x")
    grant_role(other_coordinator, other_program.pk, "program-coordinator")

    instructor = User.objects.create_user("cur03_instructor", password="x")
    InstructorAssignmentService(actor=admin).create(
        offering=offering, user=instructor, assignment_role="instructor"
    )

    syllabus_svc = SyllabusService(actor=coordinator)
    draft = syllabus_svc.create(offering=offering)
    syllabus_svc.add_learning_outcome(
        syllabus=draft, code="LO1", description="Design relational schemas", order=1
    )
    syllabus_svc.add_assessment(
        syllabus=draft, code="MT", kind="exam", order=1, max_points=Decimal("100.00")
    )

    return {
        "inst": inst,
        "admin": admin,
        "program": program,
        "other_program": other_program,
        "offering": offering,
        "po_set": po_set,
        "outcomes": outcomes,
        "other_po": other_po,
        "coordinator": coordinator,
        "other_coordinator": other_coordinator,
        "instructor": instructor,
        "draft": draft,
    }


def test_coordinator_can_set_update_list_and_delete_po_contribution_weights(cur03_world):
    """AC1: Authorized coordinator can set, update, list, and delete integer weights 1..5."""
    client = APIClient()
    client.force_authenticate(cur03_world["coordinator"])
    draft = cur03_world["draft"]
    po1 = cur03_world["outcomes"]["PO1"]
    po2 = cur03_world["outcomes"]["PO2"]

    # Set integer weights 1 through 5 across bound POs
    for w in (1, 2, 3, 4, 5):
        res = client.post(
            f"/api/v1/syllabi/{draft.pk}/po-contributions/",
            {"program_outcome": str(po1.pk), "weight": w},
            format="json",
        )
        assert res.status_code == 201, res.data
        assert res.data["weight"] == w
        assert res.data["program_outcome"] == po1.pk
        assert res.data["program_outcome_code"] == "PO1"
        assert res.data["governance_role"] == policy.COURSE_PO_WEIGHT_GOVERNANCE_ROLE
        assert res.data["governance_level"] == policy.COURSE_PO_WEIGHT_DEFAULT_LEVEL

    res2 = client.post(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/",
        {"program_outcome": str(po2.pk), "weight": 3},
        format="json",
    )
    assert res2.status_code == 201
    c2_id = res2.data["id"]

    # Patch weight
    patch_res = client.patch(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/{c2_id}/",
        {"weight": 4},
        format="json",
    )
    assert patch_res.status_code == 200
    assert patch_res.data["weight"] == 4

    # List endpoint and nested SyllabusSerializer
    list_res = client.get(f"/api/v1/syllabi/{draft.pk}/po-contributions/")
    assert list_res.status_code == 200
    assert [(row["program_outcome_code"], row["weight"]) for row in list_res.data] == [
        ("PO1", 5),
        ("PO2", 4),
    ]

    detail_res = client.get(f"/api/v1/syllabi/{draft.pk}/")
    assert detail_res.status_code == 200
    assert [
        (row["program_outcome_code"], row["weight"]) for row in detail_res.data["po_contributions"]
    ] == [("PO1", 5), ("PO2", 4)]

    # Delete removes row so PO2 becomes unmapped (NOT_ASSESSED rather than 0)
    del_res = client.delete(f"/api/v1/syllabi/{draft.pk}/po-contributions/{c2_id}/")
    assert del_res.status_code == 204
    assert not CoursePOContribution.objects.filter(pk=c2_id).exists()


@pytest.mark.parametrize(
    "invalid_weight",
    [0, -1, -2, 6, 10, 2.5, 3.5, "3.5", "0", "-2", "6", "abc", "", None, True, False],
)
def test_invalid_weights_are_rejected(cur03_world, invalid_weight):
    """AC2: Decimal, zero, negative, >5, boolean, and non-numeric values are rejected with 400."""
    client = APIClient()
    client.force_authenticate(cur03_world["coordinator"])
    draft = cur03_world["draft"]
    po1 = cur03_world["outcomes"]["PO1"]

    res = client.post(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/",
        {"program_outcome": str(po1.pk), "weight": invalid_weight},
        format="json",
    )
    assert res.status_code == 400
    assert "weight" in res.data

    with pytest.raises(ValidationError):
        SyllabusService(actor=cur03_world["coordinator"]).set_po_contribution(
            syllabus=draft, program_outcome=po1, weight=invalid_weight
        )


def test_cross_program_and_mismatched_po_set_version_rejected(cur03_world):
    """AC3: Contributions cannot point to another program's PO-set or a mismatched PO-set version."""
    client = APIClient()
    client.force_authenticate(cur03_world["coordinator"])
    draft = cur03_world["draft"]
    other_po = cur03_world["other_po"]

    # Cross-program PO rejected
    res_cross = client.post(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/",
        {"program_outcome": str(other_po.pk), "weight": 3},
        format="json",
    )
    assert res_cross.status_code == 400
    assert "program_outcome" in res_cross.data

    # Different PO-set version within same program rejected
    po_set_v2 = ProgramOutcomeSetService(actor=cur03_world["admin"]).create(
        program=cur03_world["program"], source_reference="docs/v2"
    )
    po1_v2 = ProgramOutcome.objects.create(
        outcome_set=po_set_v2,
        code="PO1",
        label="Outcome 1 v2",
        description="Updated",
        source_url="docs/v2#1",
        ordering=1,
    )
    res_version = client.post(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/",
        {"program_outcome": str(po1_v2.pk), "weight": 3},
        format="json",
    )
    assert res_version.status_code == 400
    assert "program_outcome" in res_version.data


def test_cumulative_po_attainment_formula_and_unmapped_null():
    """AC4 & AC5: (85*5 + 90*3)/8 = 86.875 -> 86.9, and no contributions -> None (NOT_ASSESSED)."""
    result = policy.compute_cumulative_po_attainment([(Decimal(85), 5), (Decimal(90), 3)])
    assert result == Decimal("86.9")

    # Works with int / float inputs as well
    assert policy.compute_cumulative_po_attainment([(85, 5), (90, 3)]) == Decimal("86.9")

    # Unmapped POs produce None (NOT_ASSESSED), never 0
    assert policy.compute_cumulative_po_attainment([]) is None

    # A single measured zero score with weight 4 produces 0.0 (distinct from unmapped None)
    assert policy.compute_cumulative_po_attainment([(Decimal(0), 4)]) == Decimal("0.0")

    # Invalid weights in calculation input raise ValidationError
    with pytest.raises(ValidationError):
        policy.compute_cumulative_po_attainment([(Decimal(85), 0)])
    with pytest.raises(ValidationError):
        policy.compute_cumulative_po_attainment([(Decimal(85), 6)])
    with pytest.raises(ValidationError):
        policy.compute_cumulative_po_attainment([(Decimal(85), 2.5)])  # type: ignore[arg-type]


def test_immutability_after_approval_and_revision_cloning_and_staleness(cur03_world):
    """AC6: Approval locks weights; revision clones them and approval bumps RevisionTracker."""
    client = APIClient()
    client.force_authenticate(cur03_world["coordinator"])
    draft = cur03_world["draft"]
    offering = cur03_world["offering"]
    program = cur03_world["program"]
    po1 = cur03_world["outcomes"]["PO1"]
    po2 = cur03_world["outcomes"]["PO2"]
    po3 = cur03_world["outcomes"]["PO3"]

    r1 = client.post(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/",
        {"program_outcome": str(po1.pk), "weight": 5},
        format="json",
    )
    assert r1.status_code == 201
    c1_id = r1.data["id"]

    r2 = client.post(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/",
        {"program_outcome": str(po2.pk), "weight": 3},
        format="json",
    )
    assert r2.status_code == 201

    # Draft with po_contributions cannot be retired as unused
    retire_res = client.post(f"/api/v1/syllabi/{draft.pk}/retire/")
    assert retire_res.status_code == 400

    # Approve version 1
    approve_res = client.post(f"/api/v1/syllabi/{draft.pk}/approve/")
    assert approve_res.status_code == 200
    offering.refresh_from_db()
    program.refresh_from_db()
    rev_offering_v1 = offering.input_revision
    rev_program_v1 = program.input_revision

    # Direct mutations on approved syllabus are rejected with 400
    assert (
        client.post(
            f"/api/v1/syllabi/{draft.pk}/po-contributions/",
            {"program_outcome": str(po3.pk), "weight": 2},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/syllabi/{draft.pk}/po-contributions/{c1_id}/",
            {"weight": 1},
            format="json",
        ).status_code
        == 400
    )
    assert client.delete(f"/api/v1/syllabi/{draft.pk}/po-contributions/{c1_id}/").status_code == 400

    # Revise creates v2 draft and clones PO contributions
    revise_res = client.post(f"/api/v1/syllabi/{draft.pk}/revise/")
    assert revise_res.status_code == 201
    v2_id = revise_res.data["id"]
    assert [
        (c["program_outcome_code"], c["weight"]) for c in revise_res.data["po_contributions"]
    ] == [("PO1", 5), ("PO2", 3)]

    # Update PO1 weight in v2 draft to 2
    res_update = client.post(
        f"/api/v1/syllabi/{v2_id}/po-contributions/",
        {"program_outcome": str(po1.pk), "weight": 2},
        format="json",
    )
    assert res_update.status_code == 201
    assert res_update.data["weight"] == 2

    # Approving v2 bumps offering and program input_revision, making prior calculations stale
    # while v1's historical snapshot remains untouched
    approve_v2 = client.post(f"/api/v1/syllabi/{v2_id}/approve/")
    assert approve_v2.status_code == 200
    offering.refresh_from_db()
    program.refresh_from_db()
    assert offering.input_revision == rev_offering_v1 + 1
    assert program.input_revision == rev_program_v1 + 1

    draft.refresh_from_db()
    assert draft.status == Syllabus.Status.RETIRED
    assert list(
        draft.po_contributions.order_by("program_outcome__ordering").values_list(
            "program_outcome__code", "weight"
        )
    ) == [("PO1", 5), ("PO2", 3)]


def test_authorization_scope_restricts_weight_mutations_to_program_coordinator(cur03_world):
    """AC7: Instructors and coordinators of other programs cannot mutate course-to-PO weights."""
    draft = cur03_world["draft"]
    po1 = cur03_world["outcomes"]["PO1"]

    coord_client = APIClient()
    coord_client.force_authenticate(cur03_world["coordinator"])
    created = coord_client.post(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/",
        {"program_outcome": str(po1.pk), "weight": 4},
        format="json",
    )
    assert created.status_code == 201
    contrib_id = created.data["id"]

    # Instructor has syllabus.draft on the offering, NOT syllabus.approve on the program
    instructor_client = APIClient()
    instructor_client.force_authenticate(cur03_world["instructor"])
    # Instructor can read weights
    assert instructor_client.get(f"/api/v1/syllabi/{draft.pk}/po-contributions/").status_code == 200
    # Instructor cannot create, update, or delete weights
    assert (
        instructor_client.post(
            f"/api/v1/syllabi/{draft.pk}/po-contributions/",
            {"program_outcome": str(po1.pk), "weight": 2},
            format="json",
        ).status_code
        == 403
    )
    assert (
        instructor_client.patch(
            f"/api/v1/syllabi/{draft.pk}/po-contributions/{contrib_id}/",
            {"weight": 2},
            format="json",
        ).status_code
        == 403
    )
    assert (
        instructor_client.delete(
            f"/api/v1/syllabi/{draft.pk}/po-contributions/{contrib_id}/"
        ).status_code
        == 403
    )

    # Coordinator of another program is out of scope (404 due to scoped queryset)
    other_coord_client = APIClient()
    other_coord_client.force_authenticate(cur03_world["other_coordinator"])
    assert other_coord_client.post(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/",
        {"program_outcome": str(po1.pk), "weight": 2},
        format="json",
    ).status_code in (403, 404)
    assert other_coord_client.patch(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/{contrib_id}/",
        {"weight": 2},
        format="json",
    ).status_code in (403, 404)
    assert other_coord_client.delete(
        f"/api/v1/syllabi/{draft.pk}/po-contributions/{contrib_id}/"
    ).status_code in (403, 404)
