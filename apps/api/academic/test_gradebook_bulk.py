from decimal import Decimal

import pytest
from access.models import RoleAssignment, Scope
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from academic.models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Grade,
    GradeBatch,
    Institution,
    Program,
    ProgramCourse,
    ProgramMembership,
)
from academic.services.grades import GradeBatchService, GradeService, GradeVersionConflict


def _grant_role(user, scope_id, role_slug):
    return RoleAssignment.objects.get_or_create(
        user=user, scope_id=scope_id, role_id=role_slug, revoked_at__isnull=True
    )[0]


@pytest.fixture
def gradebook_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("gb_admin")
    teacher = user_model.objects.create_user("gb_teacher")
    other_teacher = user_model.objects.create_user("gb_other_teacher")
    student1 = user_model.objects.create_user("gb_student1", first_name="Ada", last_name="Lovelace")
    student2 = user_model.objects.create_user("gb_student2", first_name="Alan", last_name="Turing")
    stranger = user_model.objects.create_user("gb_stranger")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Gradebook University")
    _grant_role(admin, root.pk, "administrator")

    inst = Institution.objects.create(pk=root.pk, code="GBU", name="Gradebook University")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CSE301", title="Algorithms", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CSE-BS",
        title="B.S. Computer Engineering",
        status=Program.Status.ACTIVE,
    )
    ProgramCourse.objects.create(
        program=program,
        course=course,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2026-01-01",
    )
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

    _grant_role(teacher, offering.pk, "instructor")
    _grant_role(other_teacher, other_offering.pk, "instructor")

    for stu, num in ((student1, "S201"), (student2, "S202")):
        ProgramMembership.objects.create(
            program=program,
            user=stu,
            student_number=num,
            status=ProgramMembership.Status.ACTIVE,
        )
        _grant_role(stu, offering.pk, "student")

    enrollment1 = Enrollment.objects.create(
        offering=offering, student=student1, status=Enrollment.Status.ENROLLED
    )
    enrollment2 = Enrollment.objects.create(
        offering=offering, student=student2, status=Enrollment.Status.ENROLLED
    )
    other_enrollment = Enrollment.objects.create(
        offering=other_offering, student=student1, status=Enrollment.Status.ENROLLED
    )
    midterm = Assessment.objects.create(
        offering=offering,
        title="Midterm Exam",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    project = Assessment.objects.create(
        offering=offering,
        title="Course Project",
        points_possible=Decimal("50.00"),
        status=Assessment.Status.APPROVED,
    )
    other_assessment = Assessment.objects.create(
        offering=other_offering,
        title="Other Midterm",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    batch = GradeBatch.objects.create(offering=offering, name="Main Batch")
    other_batch = GradeBatch.objects.create(offering=other_offering, name="Other Batch")

    return {
        "admin": admin,
        "teacher": teacher,
        "other_teacher": other_teacher,
        "student1": student1,
        "student2": student2,
        "stranger": stranger,
        "program": program,
        "offering": offering,
        "other_offering": other_offering,
        "enrollment1": enrollment1,
        "enrollment2": enrollment2,
        "other_enrollment": other_enrollment,
        "midterm": midterm,
        "project": project,
        "other_assessment": other_assessment,
        "batch": batch,
        "other_batch": other_batch,
    }


def test_bulk_save_creates_and_updates_student_assessment_matrix_cells_and_persists(
    gradebook_world,
):
    client = APIClient()
    client.force_authenticate(gradebook_world["teacher"])

    payload = {
        "offering": str(gradebook_world["offering"].pk),
        "expected_input_revision": gradebook_world["offering"].input_revision,
        "idempotency_key": "bulk-matrix-1",
        "items": [
            {
                "enrollment": str(gradebook_world["enrollment1"].pk),
                "assessment": str(gradebook_world["midterm"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "0.00",
                "reason": "",
            },
            {
                "enrollment": str(gradebook_world["enrollment1"].pk),
                "assessment": str(gradebook_world["project"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "missing",
                "points_earned": None,
                "reason": "",
            },
            {
                "enrollment": str(gradebook_world["enrollment2"].pk),
                "assessment": str(gradebook_world["midterm"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "exempt",
                "points_earned": None,
                "reason": "",
            },
            {
                "enrollment": str(gradebook_world["enrollment2"].pk),
                "assessment": str(gradebook_world["project"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "45.50",
                "reason": "",
            },
        ],
    }

    res = client.post("/api/v1/grades/bulk/", payload, format="json")
    assert res.status_code == 200, res.data
    assert res["Cache-Control"] == "no-store"
    assert res.data["offering"] == str(gradebook_world["offering"].pk)
    assert res.data["idempotency_key"] == "bulk-matrix-1"
    assert len(res.data["grades"]) == 4

    # Reload via GET /api/v1/grades/ and verify distinct states
    list_res = client.get(f"/api/v1/grades/?offering={gradebook_world['offering'].pk}")
    assert list_res.status_code == 200
    by_cell = {(str(g["enrollment"]), str(g["assessment"])): g for g in list_res.data["results"]}

    c1_mid = by_cell[(str(gradebook_world["enrollment1"].pk), str(gradebook_world["midterm"].pk))]
    assert c1_mid["state"] == "scored"
    assert c1_mid["points_earned"] == "0.00"
    assert c1_mid["version"] == 1

    c1_proj = by_cell[(str(gradebook_world["enrollment1"].pk), str(gradebook_world["project"].pk))]
    assert c1_proj["state"] == "missing"
    assert c1_proj["points_earned"] is None

    c2_mid = by_cell[(str(gradebook_world["enrollment2"].pk), str(gradebook_world["midterm"].pk))]
    assert c2_mid["state"] == "exempt"
    assert c2_mid["points_earned"] is None

    c2_proj = by_cell[(str(gradebook_world["enrollment2"].pk), str(gradebook_world["project"].pk))]
    assert c2_proj["state"] == "scored"
    assert c2_proj["points_earned"] == "45.50"

    # Idempotent replay with same payload does not bump versions or duplicate history
    replay = client.post("/api/v1/grades/bulk/", payload, format="json")
    assert replay.status_code == 200
    assert all(g["version"] == 1 for g in replay.data["grades"])

    # Update existing cell and verify version bump to 2
    update_payload = {
        "offering": str(gradebook_world["offering"].pk),
        "expected_input_revision": gradebook_world["offering"].input_revision,
        "idempotency_key": "bulk-matrix-2",
        "items": [
            {
                "enrollment": str(gradebook_world["enrollment1"].pk),
                "assessment": str(gradebook_world["project"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "42.00",
                "reason": "Late submission accepted",
                "expected_version": 1,
            }
        ],
    }
    upd_res = client.post("/api/v1/grades/bulk/", update_payload, format="json")
    assert upd_res.status_code == 200
    assert upd_res.data["grades"][0]["version"] == 2
    assert upd_res.data["grades"][0]["state"] == "scored"
    assert upd_res.data["grades"][0]["points_earned"] == "42.00"


def test_bulk_save_rejects_invalid_cell_atomically_without_partial_updates(gradebook_world):
    client = APIClient()
    client.force_authenticate(gradebook_world["teacher"])

    # Seed one existing grade
    existing = GradeService(actor=gradebook_world["teacher"]).create(
        enrollment=gradebook_world["enrollment1"],
        assessment=gradebook_world["midterm"],
        batch=gradebook_world["batch"],
        state=Grade.State.SCORED,
        points_earned=Decimal("80.00"),
    )

    # Batch with one valid update + one invalid cell (points > points_possible)
    bad_payload = {
        "offering": str(gradebook_world["offering"].pk),
        "expected_input_revision": gradebook_world["offering"].input_revision,
        "idempotency_key": "bulk-invalid-1",
        "items": [
            {
                "enrollment": str(gradebook_world["enrollment1"].pk),
                "assessment": str(gradebook_world["midterm"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "90.00",
                "expected_version": 1,
            },
            {
                "enrollment": str(gradebook_world["enrollment2"].pk),
                "assessment": str(gradebook_world["project"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "55.00",  # project max is 50.00
            },
        ],
    }
    res = client.post("/api/v1/grades/bulk/", bad_payload, format="json")
    assert res.status_code == 400
    assert "items" in res.data

    # Ensure existing grade was NOT partially updated and no new grade was created
    existing.refresh_from_db()
    assert existing.points_earned == Decimal("80.00")
    assert existing.version == 1
    assert Grade.objects.count() == 1


def test_bulk_save_released_batch_requires_reason_and_bumps_revision(gradebook_world):
    client = APIClient()
    client.force_authenticate(gradebook_world["teacher"])

    GradeBatchService(actor=gradebook_world["teacher"]).release(batch=gradebook_world["batch"])
    gradebook_world["offering"].refresh_from_db()
    rev_before = gradebook_world["offering"].input_revision

    # Missing reason on released batch -> 400 and no write
    no_reason_payload = {
        "offering": str(gradebook_world["offering"].pk),
        "expected_input_revision": rev_before,
        "idempotency_key": "bulk-rel-1",
        "items": [
            {
                "enrollment": str(gradebook_world["enrollment1"].pk),
                "assessment": str(gradebook_world["midterm"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "75.00",
                "reason": "   ",
            }
        ],
    }
    res_fail = client.post("/api/v1/grades/bulk/", no_reason_payload, format="json")
    assert res_fail.status_code == 400
    assert Grade.objects.count() == 0

    with_reason_payload = {
        **no_reason_payload,
        "idempotency_key": "bulk-rel-2",
        "items": [
            {
                **no_reason_payload["items"][0],
                "reason": "Authorized post-release entry",
            }
        ],
    }
    res_ok = client.post("/api/v1/grades/bulk/", with_reason_payload, format="json")
    assert res_ok.status_code == 200
    gradebook_world["offering"].refresh_from_db()
    assert gradebook_world["offering"].input_revision == rev_before + 1
    assert res_ok.data["input_revision"] == rev_before + 1


def test_bulk_save_version_and_revision_conflicts_return_409(gradebook_world):
    client = APIClient()
    client.force_authenticate(gradebook_world["teacher"])

    grade = GradeService(actor=gradebook_world["teacher"]).create(
        enrollment=gradebook_world["enrollment1"],
        assessment=gradebook_world["midterm"],
        batch=gradebook_world["batch"],
        state=Grade.State.SCORED,
        points_earned=Decimal("70.00"),
    )
    GradeService(actor=gradebook_world["teacher"]).correct(
        grade=grade,
        expected_version=1,
        state=Grade.State.SCORED,
        points_earned=Decimal("75.00"),
    )

    # Stale expected_version (1 instead of 2) returns 409 Conflict and mutates nothing
    stale_version_payload = {
        "offering": str(gradebook_world["offering"].pk),
        "idempotency_key": "bulk-conflict-1",
        "items": [
            {
                "enrollment": str(gradebook_world["enrollment1"].pk),
                "assessment": str(gradebook_world["midterm"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "85.00",
                "expected_version": 1,
            },
            {
                "enrollment": str(gradebook_world["enrollment2"].pk),
                "assessment": str(gradebook_world["project"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "40.00",
            },
        ],
    }
    res_v = client.post("/api/v1/grades/bulk/", stale_version_payload, format="json")
    assert res_v.status_code == 409
    assert res_v.data["code"] == "version_conflict"
    assert res_v.data["current_version"] == 2
    grade.refresh_from_db()
    assert grade.points_earned == Decimal("75.00")
    assert Grade.objects.count() == 1

    # Stale expected_input_revision returns 409 Conflict
    stale_rev_payload = {
        "offering": str(gradebook_world["offering"].pk),
        "expected_input_revision": gradebook_world["offering"].input_revision + 5,
        "idempotency_key": "bulk-conflict-2",
        "items": [
            {
                "enrollment": str(gradebook_world["enrollment2"].pk),
                "assessment": str(gradebook_world["project"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "40.00",
            }
        ],
    }
    res_r = client.post("/api/v1/grades/bulk/", stale_rev_payload, format="json")
    assert res_r.status_code == 409
    assert res_r.data["code"] == "version_conflict"
    assert res_r.data["current_input_revision"] == gradebook_world["offering"].input_revision
    assert Grade.objects.count() == 1


def test_bulk_save_authorization_and_cross_offering_rejection(gradebook_world):
    base_payload = {
        "offering": str(gradebook_world["offering"].pk),
        "idempotency_key": "bulk-auth-1",
        "items": [
            {
                "enrollment": str(gradebook_world["enrollment1"].pk),
                "assessment": str(gradebook_world["midterm"].pk),
                "batch": str(gradebook_world["batch"].pk),
                "state": "scored",
                "points_earned": "90.00",
            }
        ],
    }

    for unauthorized in (
        gradebook_world["stranger"],
        gradebook_world["student1"],
        gradebook_world["other_teacher"],
    ):
        c = APIClient()
        c.force_authenticate(unauthorized)
        res = c.post("/api/v1/grades/bulk/", base_payload, format="json")
        assert res.status_code == 403
    assert Grade.objects.count() == 0

    # Authorized instructor attempting to include cross-offering enrollment, assessment, or batch
    teacher_client = APIClient()
    teacher_client.force_authenticate(gradebook_world["teacher"])

    cross_enrollment_payload = {
        **base_payload,
        "items": [
            {
                **base_payload["items"][0],
                "enrollment": str(gradebook_world["other_enrollment"].pk),
            }
        ],
    }
    assert (
        teacher_client.post(
            "/api/v1/grades/bulk/", cross_enrollment_payload, format="json"
        ).status_code
        == 400
    )

    cross_assessment_payload = {
        **base_payload,
        "items": [
            {
                **base_payload["items"][0],
                "assessment": str(gradebook_world["other_assessment"].pk),
            }
        ],
    }
    assert (
        teacher_client.post(
            "/api/v1/grades/bulk/", cross_assessment_payload, format="json"
        ).status_code
        == 400
    )

    cross_batch_payload = {
        **base_payload,
        "items": [
            {
                **base_payload["items"][0],
                "batch": str(gradebook_world["other_batch"].pk),
            }
        ],
    }
    assert (
        teacher_client.post("/api/v1/grades/bulk/", cross_batch_payload, format="json").status_code
        == 400
    )
    assert Grade.objects.count() == 0


def test_bulk_save_duplicate_pair_in_payload_and_nonexistent_expected_version(gradebook_world):
    svc = GradeService(actor=gradebook_world["teacher"])
    item = {
        "enrollment": gradebook_world["enrollment1"],
        "assessment": gradebook_world["midterm"],
        "batch": gradebook_world["batch"],
        "state": Grade.State.SCORED,
        "points_earned": Decimal("50.00"),
    }
    with pytest.raises(ValidationError):
        svc.bulk_save(
            offering=gradebook_world["offering"],
            items=[item, item],
            idempotency_key="dup-key",
        )

    with pytest.raises(GradeVersionConflict):
        svc.bulk_save(
            offering=gradebook_world["offering"],
            items=[{**item, "expected_version": 1}],
            idempotency_key="bad-expected-ver",
        )
