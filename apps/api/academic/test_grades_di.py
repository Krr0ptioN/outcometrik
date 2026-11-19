from decimal import Decimal

import pytest
from access.models import RoleAssignment, Scope
from access.policy import AuthorizationService
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework.test import APIClient, APIRequestFactory
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.controllers.grades import GradeBatchController, GradeController
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
def grades_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("grade_admin")
    teacher = user_model.objects.create_user("grade_teacher")
    student1 = user_model.objects.create_user("grade_student1")
    student2 = user_model.objects.create_user("grade_student2")
    stranger = user_model.objects.create_user("grade_stranger")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Grades University")
    _grant_role(admin, root.pk, "administrator")

    inst = Institution.objects.create(pk=root.pk, code="GU", name="Grades University")
    dept = Department.objects.create(institution=inst, code="CS", name="Computer Science")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CS350", title="Systems Engineering", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CS-BS",
        title="B.S. in Computer Science",
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

    for stu, num in ((student1, "S101"), (student2, "S102")):
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
    assessment = Assessment.objects.create(
        offering=offering,
        title="Final Exam",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    quiz = Assessment.objects.create(
        offering=offering,
        title="Quiz 1",
        points_possible=Decimal("20.00"),
        status=Assessment.Status.APPROVED,
    )
    batch = GradeBatch.objects.create(offering=offering, name="Final")

    return {
        "admin": admin,
        "teacher": teacher,
        "student1": student1,
        "student2": student2,
        "stranger": stranger,
        "inst": inst,
        "dept": dept,
        "term": term,
        "program": program,
        "offering": offering,
        "other_offering": other_offering,
        "enrollment1": enrollment1,
        "enrollment2": enrollment2,
        "assessment": assessment,
        "quiz": quiz,
        "batch": batch,
    }


def test_grade_services_registered_in_wireup():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        grade_svc = scoped.get(GradeService)
        assert isinstance(grade_svc, GradeService)
        assert isinstance(grade_svc.auth_service, AuthorizationService)

        batch_svc = scoped.get(GradeBatchService)
        assert isinstance(batch_svc, GradeBatchService)
        assert isinstance(batch_svc.auth_service, AuthorizationService)


def test_grade_controllers_constructor_injection_and_cache_control():
    grade_ctrl = GradeController()
    assert isinstance(grade_ctrl.service, GradeService)

    batch_ctrl = GradeBatchController()
    assert isinstance(batch_ctrl.service, GradeBatchService)

    custom_auth = AuthorizationService()
    custom_grade_svc = GradeService(auth_service=custom_auth)
    custom_batch_svc = GradeBatchService(auth_service=custom_auth)
    assert GradeController(service=custom_grade_svc).service is custom_grade_svc
    assert GradeBatchController(service=custom_batch_svc).service is custom_batch_svc

    rf = APIRequestFactory()
    for ctrl_cls, path in (
        (GradeController, "/api/v1/grades/"),
        (GradeBatchController, "/api/v1/grade-batches/"),
    ):
        ctrl = ctrl_cls()
        ctrl.headers = {}
        finalized = ctrl.finalize_response(rf.get(path), HttpResponse())
        assert finalized["Cache-Control"] == "no-store"


def test_grade_service_scoping_filtering_and_actor_override(grades_world):
    svc = GradeService()
    g1 = svc.create(
        enrollment=grades_world["enrollment1"],
        assessment=grades_world["assessment"],
        batch=grades_world["batch"],
        state=Grade.State.SCORED,
        points_earned=Decimal("85.00"),
        actor=grades_world["teacher"],
    )
    g2 = svc.create(
        enrollment=grades_world["enrollment2"],
        assessment=grades_world["quiz"],
        batch=grades_world["batch"],
        state=Grade.State.SCORED,
        points_earned=Decimal("18.00"),
        actor=grades_world["teacher"],
    )

    assert not svc.get_queryset().exists()
    assert not svc.get_queryset(actor=AnonymousUser()).exists()
    assert not svc.get_queryset(actor=grades_world["stranger"]).exists()
    assert not svc.get_queryset(actor=grades_world["student1"]).exists()

    teacher_qs = list(svc.get_queryset(actor=grades_world["teacher"], page="1", unknown="ignored"))
    assert teacher_qs == [g1, g2]

    filtered_qs = list(
        svc.get_queryset(actor=grades_world["teacher"], assessment=grades_world["quiz"])
    )
    assert filtered_qs == [g2]

    batch_svc = GradeBatchService()
    batch_svc.release(batch=grades_world["batch"], actor=grades_world["teacher"])
    grades_world["batch"].refresh_from_db()
    assert grades_world["batch"].released_by == grades_world["teacher"]

    assert list(svc.get_queryset(actor=grades_world["student1"])) == [g1]
    assert list(svc.get_queryset(actor=grades_world["student2"])) == [g2]
    assert list(svc.get_queryset(actor=grades_world["admin"])) == [g1, g2]


def test_grade_batch_service_crud_immutability_and_release(grades_world):
    batch_svc = GradeBatchService()
    created = batch_svc.create(offering=grades_world["offering"], name="Midterm")
    assert created.pk is not None

    # Duplicate (offering, name) maps IntegrityError to ValidationError
    with pytest.raises(ValidationError):
        batch_svc.create(offering=grades_world["offering"], name="Midterm")

    # Immutability on offering
    with pytest.raises(ValidationError) as exc:
        batch_svc.update(instance=created, offering=grades_world["other_offering"])
    assert "offering" in exc.value.message_dict

    updated = batch_svc.update(instance=created, name="Midterm Revised")
    assert updated.name == "Midterm Revised"

    # Actor scoping
    assert list(batch_svc.get_queryset(actor=grades_world["teacher"])) == [
        grades_world["batch"],
        updated,
    ]
    assert not batch_svc.get_queryset(actor=grades_world["student1"]).exists()
    assert not batch_svc.get_queryset(actor=grades_world["stranger"]).exists()

    # Release sets released_by and is idempotent
    released = batch_svc.release(batch=updated, actor=grades_world["teacher"])
    assert released.released_at is not None
    assert released.released_by == grades_world["teacher"]


def test_grade_service_mutations_conflict_and_history(grades_world):
    svc = GradeService()
    grade = svc.create(
        enrollment=grades_world["enrollment1"],
        assessment=grades_world["assessment"],
        batch=grades_world["batch"],
        state=Grade.State.SCORED,
        points_earned=Decimal("75.00"),
        actor=grades_world["teacher"],
    )
    assert grade.version == 1
    assert grade.history.get().changed_by == grades_world["teacher"]

    updated = svc.correct(
        grade=grade,
        expected_version=1,
        state=Grade.State.SCORED,
        points_earned=Decimal("82.00"),
        reason="Curve adjustment",
        actor=grades_world["admin"],
    )
    assert updated.version == 2
    assert list(svc.history(grade=updated).values_list("version", "changed_by_id")) == [
        (1, grades_world["teacher"].pk),
        (2, grades_world["admin"].pk),
    ]

    with pytest.raises(GradeVersionConflict) as exc:
        svc.correct(
            grade=updated,
            expected_version=1,
            state=Grade.State.SCORED,
            points_earned=Decimal("90.00"),
            actor=grades_world["teacher"],
        )
    assert exc.value.current_version == 2


def test_grade_api_guards_conflict_and_scoping(grades_world):
    teacher_client = APIClient()
    teacher_client.force_authenticate(grades_world["teacher"])

    student1_client = APIClient()
    student1_client.force_authenticate(grades_world["student1"])

    student2_client = APIClient()
    student2_client.force_authenticate(grades_world["student2"])

    stranger_client = APIClient()
    stranger_client.force_authenticate(grades_world["stranger"])

    # GradeBatch creation guarded by @require_permission("grades.edit", scope_field="offering")
    batch_payload = {"offering": str(grades_world["offering"].pk), "name": "Lab 1"}
    assert (
        stranger_client.post("/api/v1/grade-batches/", batch_payload, format="json").status_code
        == 403
    )
    assert (
        student1_client.post("/api/v1/grade-batches/", batch_payload, format="json").status_code
        == 403
    )

    r_batch = teacher_client.post("/api/v1/grade-batches/", batch_payload, format="json")
    assert r_batch.status_code == 201
    assert r_batch["Cache-Control"] == "no-store"
    batch_id = r_batch.data["id"]

    # GradeBatch queryset scoping
    assert teacher_client.get("/api/v1/grade-batches/").data["count"] == 2
    assert student1_client.get("/api/v1/grade-batches/").data["count"] == 0
    assert stranger_client.get(f"/api/v1/grade-batches/{batch_id}/").status_code == 404

    # Disallowed methods on GradeBatch detail
    assert (
        teacher_client.patch(
            f"/api/v1/grade-batches/{batch_id}/", {"name": "X"}, format="json"
        ).status_code
        == 405
    )
    assert teacher_client.delete(f"/api/v1/grade-batches/{batch_id}/").status_code == 405

    # Grade creation guarded by @require_permission("grades.edit", scope_field="enrollment.offering")
    grade_payload = {
        "enrollment": str(grades_world["enrollment1"].pk),
        "assessment": str(grades_world["assessment"].pk),
        "batch": batch_id,
        "state": "scored",
        "points_earned": "88.50",
    }
    assert stranger_client.post("/api/v1/grades/", grade_payload, format="json").status_code == 403
    assert student1_client.post("/api/v1/grades/", grade_payload, format="json").status_code == 403

    r_grade = teacher_client.post("/api/v1/grades/", grade_payload, format="json")
    assert r_grade.status_code == 201
    assert r_grade["Cache-Control"] == "no-store"
    grade_id = r_grade.data["id"]
    grade = Grade.objects.get(pk=grade_id)
    assert grade.history.get().changed_by == grades_world["teacher"]

    # Unreleased grade hidden from students, visible to teacher
    assert student1_client.get(f"/api/v1/grades/{grade_id}/").status_code == 404
    assert teacher_client.get(f"/api/v1/grades/{grade_id}/").status_code == 200

    # Grade PATCH optimistic concurrency conflict (409) & guard
    patch_body = {"expected_version": 1, "state": "scored", "points_earned": "91.00"}
    r_patch = teacher_client.patch(f"/api/v1/grades/{grade_id}/", patch_body, format="json")
    assert r_patch.status_code == 200
    assert r_patch.data["version"] == 2
    assert r_patch["Cache-Control"] == "no-store"

    r_conflict = teacher_client.patch(f"/api/v1/grades/{grade_id}/", patch_body, format="json")
    assert r_conflict.status_code == 409
    assert r_conflict.data == {
        "code": "version_conflict",
        "detail": "The grade was changed by someone else.",
        "current_version": 2,
    }

    # Disallowed methods on Grade detail
    assert (
        teacher_client.put(f"/api/v1/grades/{grade_id}/", patch_body, format="json").status_code
        == 405
    )
    assert teacher_client.delete(f"/api/v1/grades/{grade_id}/").status_code == 405

    # Batch release guard & execution
    assert student1_client.post(f"/api/v1/grade-batches/{batch_id}/release/").status_code == 404
    assert stranger_client.post(f"/api/v1/grade-batches/{batch_id}/release/").status_code == 404
    r_release = teacher_client.post(f"/api/v1/grade-batches/{batch_id}/release/")
    assert r_release.status_code == 200
    assert r_release.data["released_at"] is not None
    assert GradeBatch.objects.get(pk=batch_id).released_by == grades_world["teacher"]

    # Released grade: owning student can read, other student cannot, student cannot patch or read history
    assert student1_client.get(f"/api/v1/grades/{grade_id}/").status_code == 200
    assert student2_client.get(f"/api/v1/grades/{grade_id}/").status_code == 404
    assert (
        student1_client.patch(
            f"/api/v1/grades/{grade_id}/",
            {"expected_version": 2, "state": "scored", "points_earned": "99.00", "reason": "hack"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        stranger_client.patch(
            f"/api/v1/grades/{grade_id}/",
            {"expected_version": 2, "state": "scored", "points_earned": "99.00", "reason": "hack"},
            format="json",
        ).status_code
        == 404
    )

    assert student1_client.get(f"/api/v1/grades/{grade_id}/history/").status_code == 403
    assert stranger_client.get(f"/api/v1/grades/{grade_id}/history/").status_code == 404
    r_history = teacher_client.get(f"/api/v1/grades/{grade_id}/history/")
    assert r_history.status_code == 200
    assert len(r_history.data) == 2
