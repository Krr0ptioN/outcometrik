from decimal import Decimal

import pytest
from access.models import AuditEvent, Capability, DirectCapabilityGrant, RoleAssignment, Scope
from access.policy import AuthorizationService
from access.services import assign, revoke
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    GradeBatch,
    Institution,
    Program,
    ProgramCourse,
    ProgramMembership,
)
from academic.services import CourseOfferingService, EnrollmentService, WorkspaceService
from academic.services.grades import GradeBatchService, GradeService

pytestmark = pytest.mark.django_db


def _grant_role(user, scope_id, role_slug):
    return RoleAssignment.objects.get_or_create(
        user=user, scope_id=scope_id, role_id=role_slug, revoked_at__isnull=True
    )[0]


@pytest.fixture
def auth02_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("auth02_admin")
    delegate = user_model.objects.create_user("auth02_delegate")  # starts with NO roles
    instructor = user_model.objects.create_user("auth02_instructor")
    coordinator = user_model.objects.create_user("auth02_coordinator")
    student1 = user_model.objects.create_user(
        "auth02_student1", first_name="Ada", last_name="Lovelace"
    )
    student2 = user_model.objects.create_user(
        "auth02_student2", first_name="Alan", last_name="Turing"
    )
    outsider = user_model.objects.create_user("auth02_outsider")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="AUTH-02 University")
    _grant_role(admin, root.pk, "administrator")

    inst = Institution.objects.create(pk=root.pk, code="A02U", name="AUTH-02 University")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CSE302", title="Operating Systems", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CSE-BS",
        title="B.S. in Computer Engineering",
        status=Program.Status.ACTIVE,
    )
    ProgramCourse.objects.create(
        program=program,
        course=course,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2026-01-01",
    )

    offering_a = CourseOffering.objects.create(
        program=program,
        course=course,
        term=term,
        section="01",
        status=CourseOffering.Status.ACTIVE,
    )
    offering_b = CourseOffering.objects.create(
        program=program,
        course=course,
        term=term,
        section="02",
        status=CourseOffering.Status.ACTIVE,
    )

    _grant_role(coordinator, program.pk, "program-coordinator")
    _grant_role(instructor, offering_a.pk, "instructor")

    for stu, num in ((student1, "S201"), (student2, "S202")):
        ProgramMembership.objects.create(
            program=program,
            user=stu,
            student_number=num,
            status=ProgramMembership.Status.ACTIVE,
        )
        _grant_role(stu, offering_a.pk, "student")
        _grant_role(stu, offering_b.pk, "student")

    enrollment_a1 = Enrollment.objects.create(
        offering=offering_a, student=student1, status=Enrollment.Status.ENROLLED
    )
    enrollment_a2 = Enrollment.objects.create(
        offering=offering_a, student=student2, status=Enrollment.Status.ENROLLED
    )
    enrollment_b1 = Enrollment.objects.create(
        offering=offering_b, student=student1, status=Enrollment.Status.ENROLLED
    )

    assessment_a = Assessment.objects.create(
        offering=offering_a,
        title="Midterm Exam A",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    assessment_b = Assessment.objects.create(
        offering=offering_b,
        title="Midterm Exam B",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )

    batch_a = GradeBatch.objects.create(offering=offering_a, name="Midterm A")
    batch_b = GradeBatch.objects.create(offering=offering_b, name="Midterm B")

    return {
        "admin": admin,
        "delegate": delegate,
        "instructor": instructor,
        "coordinator": coordinator,
        "student1": student1,
        "student2": student2,
        "outsider": outsider,
        "inst": inst,
        "dept": dept,
        "term": term,
        "course": course,
        "program": program,
        "offering_a": offering_a,
        "offering_b": offering_b,
        "enrollment_a1": enrollment_a1,
        "enrollment_a2": enrollment_a2,
        "enrollment_b1": enrollment_b1,
        "assessment_a": assessment_a,
        "assessment_b": assessment_b,
        "batch_a": batch_a,
        "batch_b": batch_b,
    }


def test_auth02_wireup_di_services_resolve_with_direct_grants(auth02_world):
    """Verify Wireup DI container resolves services and honors direct capability grants."""
    delegate = auth02_world["delegate"]
    offering_a = auth02_world["offering_a"]
    offering_b = auth02_world["offering_b"]

    assign(
        actor=auth02_world["admin"],
        user=delegate,
        scope=Scope.objects.get(pk=offering_a.pk),
        capability=Capability.objects.get(pk="grades.edit"),
    )

    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        auth_svc = scoped.get(AuthorizationService)
        ws_svc = scoped.get(WorkspaceService)
        off_svc = scoped.get(CourseOfferingService)
        enr_svc = scoped.get(EnrollmentService)
        grade_svc = scoped.get(GradeService)
        batch_svc = scoped.get(GradeBatchService)

        assert auth_svc.allows(
            principal=delegate,
            capability="grades.edit",
            scope=Scope.objects.get(pk=offering_a.pk),
        )
        assert not auth_svc.allows(
            principal=delegate,
            capability="grades.edit",
            scope=Scope.objects.get(pk=offering_b.pk),
        )

        assert list(ws_svc.instructor_offerings(actor=delegate)) == [offering_a]
        assert list(off_svc.get_queryset(actor=delegate)) == [offering_a]
        assert set(enr_svc.get_queryset(actor=delegate)) == {
            auth02_world["enrollment_a1"],
            auth02_world["enrollment_a2"],
        }
        assert list(batch_svc.get_queryset(actor=delegate)) == [auth02_world["batch_a"]]
        assert grade_svc.get_queryset(actor=delegate).count() == 0


def test_auth02_grant_and_exercise_without_role_end_to_end(auth02_world):
    """1. User with no roles is granted grades.edit on Offering A and exercises it via HTTP API."""
    admin = auth02_world["admin"]
    delegate = auth02_world["delegate"]
    offering_a = auth02_world["offering_a"]
    offering_b = auth02_world["offering_b"]

    assert not RoleAssignment.objects.filter(user=delegate, revoked_at__isnull=True).exists()

    admin_client = APIClient()
    admin_client.force_authenticate(admin)

    delegate_client = APIClient()
    delegate_client.force_authenticate(delegate)

    # Before grant: delegate cannot access instructor workspace or offerings
    assert delegate_client.get("/api/v1/workspaces/instructor/").status_code == 403
    assert delegate_client.get("/api/v1/offerings/").data["count"] == 0
    assert delegate_client.get(f"/api/v1/offerings/{offering_a.pk}/").status_code == 404

    # Administrator grants grades.edit directly on Offering A via HTTP API
    grant_res = admin_client.post(
        "/api/access/assignments/",
        {
            "user": delegate.pk,
            "scope": str(offering_a.pk),
            "capability": "grades.edit",
        },
        format="json",
    )
    assert grant_res.status_code == 201, grant_res.data
    grant_id = grant_res.data["id"]

    # Delegate sees Offering A (and its roster) in instructor workspace
    ws_res = delegate_client.get("/api/v1/workspaces/instructor/")
    assert ws_res.status_code == 200, ws_res.data
    assert [o["id"] for o in ws_res.data["offerings"]] == [str(offering_a.pk)]
    assert len(ws_res.data["offerings"][0]["roster"]) == 2

    # Delegate sees Offering A in offerings list and detail, but not Offering B
    off_list = delegate_client.get("/api/v1/offerings/")
    assert off_list.status_code == 200
    assert [o["id"] for o in off_list.data["results"]] == [str(offering_a.pk)]
    assert delegate_client.get(f"/api/v1/offerings/{offering_a.pk}/").status_code == 200
    assert delegate_client.get(f"/api/v1/offerings/{offering_b.pk}/").status_code == 404

    # Delegate lists enrollments for Offering A, and sees 0 for Offering B
    enr_a = delegate_client.get(f"/api/v1/enrollments/?offering={offering_a.pk}")
    assert enr_a.status_code == 200
    assert enr_a.data["count"] == 2
    enr_nested_a = delegate_client.get(f"/api/v1/offerings/{offering_a.pk}/enrollments/")
    assert enr_nested_a.status_code == 200
    assert enr_nested_a.data["count"] == 2

    enr_b = delegate_client.get(f"/api/v1/enrollments/?offering={offering_b.pk}")
    assert enr_b.status_code == 200
    assert enr_b.data["count"] == 0
    assert delegate_client.get(f"/api/v1/offerings/{offering_b.pk}/enrollments/").status_code == 404

    # Delegate creates a grade batch and enters/updates grades on Offering A
    batch_create = delegate_client.post(
        "/api/v1/grade-batches/",
        {"offering": str(offering_a.pk), "name": "Quiz Batch A"},
        format="json",
    )
    assert batch_create.status_code == 201, batch_create.data
    created_batch_id = batch_create.data["id"]

    grade_create = delegate_client.post(
        "/api/v1/grades/",
        {
            "enrollment": str(auth02_world["enrollment_a1"].pk),
            "assessment": str(auth02_world["assessment_a"].pk),
            "batch": created_batch_id,
            "state": "scored",
            "points_earned": "92.50",
        },
        format="json",
    )
    assert grade_create.status_code == 201, grade_create.data
    grade_id = grade_create.data["id"]

    grade_patch = delegate_client.patch(
        f"/api/v1/grades/{grade_id}/",
        {
            "expected_version": 1,
            "state": "scored",
            "points_earned": "95.00",
        },
        format="json",
    )
    assert grade_patch.status_code == 200, grade_patch.data
    assert grade_patch.data["points_earned"] == "95.00"

    # Delegate is denied (403/404) when attempting to view or edit grades/batches on Offering B
    batch_b_Attempt = delegate_client.post(
        "/api/v1/grade-batches/",
        {"offering": str(offering_b.pk), "name": "Unauthorized Batch B"},
        format="json",
    )
    assert batch_b_Attempt.status_code == 403

    grade_b_attempt = delegate_client.post(
        "/api/v1/grades/",
        {
            "enrollment": str(auth02_world["enrollment_b1"].pk),
            "assessment": str(auth02_world["assessment_b"].pk),
            "batch": str(auth02_world["batch_b"].pk),
            "state": "scored",
            "points_earned": "80.00",
        },
        format="json",
    )
    assert grade_b_attempt.status_code == 403
    assert (
        delegate_client.get(f"/api/v1/grade-batches/{auth02_world['batch_b'].pk}/").status_code
        == 404
    )

    # Revoke the direct grant and verify access is immediately removed
    revoke_res = admin_client.delete(f"/api/access/grants/{grant_id}/")
    assert revoke_res.status_code == 204
    assert delegate_client.get("/api/v1/workspaces/instructor/").status_code == 403
    assert delegate_client.get(f"/api/v1/offerings/{offering_a.pk}/").status_code == 404
    assert delegate_client.get(f"/api/v1/grades/{grade_id}/").status_code == 404


def test_auth02_exact_scope_boundary_no_program_to_offering_inheritance(auth02_world):
    """2. Direct grant of grades.edit on program scope does NOT inherit to offerings in that program."""
    admin = auth02_world["admin"]
    delegate = auth02_world["delegate"]
    program = auth02_world["program"]
    offering_a = auth02_world["offering_a"]

    grant = assign(
        actor=admin,
        user=delegate,
        scope=Scope.objects.get(pk=program.pk),
        capability=Capability.objects.get(pk="grades.edit"),
    )
    auth_svc = AuthorizationService()
    assert auth_svc.allows(
        principal=delegate,
        capability="grades.edit",
        scope=Scope.objects.get(pk=program.pk),
    )
    assert not auth_svc.allows(
        principal=delegate,
        capability="grades.edit",
        scope=Scope.objects.get(pk=offering_a.pk),
    )

    delegate_client = APIClient()
    delegate_client.force_authenticate(delegate)

    # Program-scoped direct grant of grades.edit must NOT expose offering_a in instructor workspace or offerings
    assert delegate_client.get("/api/v1/workspaces/instructor/").status_code == 403
    assert delegate_client.get("/api/v1/offerings/").data["count"] == 0
    assert delegate_client.get(f"/api/v1/offerings/{offering_a.pk}/").status_code == 404
    assert delegate_client.get(f"/api/v1/enrollments/?offering={offering_a.pk}").data["count"] == 0

    # Program-scoped direct grant of grades.edit must NOT allow creating grade batches or grades on offering_a
    assert (
        delegate_client.post(
            "/api/v1/grade-batches/",
            {"offering": str(offering_a.pk), "name": "Program Inherit Attempt"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        delegate_client.post(
            "/api/v1/grades/",
            {
                "enrollment": str(auth02_world["enrollment_a1"].pk),
                "assessment": str(auth02_world["assessment_a"].pk),
                "batch": str(auth02_world["batch_a"].pk),
                "state": "scored",
                "points_earned": "85.00",
            },
            format="json",
        ).status_code
        == 403
    )

    revoke(actor=admin, assignment=grant)


def test_auth02_overlapping_role_and_direct_grant_revocation(auth02_world):
    """3. Overlapping instructor role and direct grades.edit grant preserve access until both are revoked."""
    admin = auth02_world["admin"]
    delegate = auth02_world["delegate"]
    offering_a = auth02_world["offering_a"]

    admin_client = APIClient()
    admin_client.force_authenticate(admin)

    delegate_client = APIClient()
    delegate_client.force_authenticate(delegate)

    # Scenario A: Grant both instructor role and direct grades.edit grant, revoke direct grant first
    role_res = admin_client.post(
        "/api/access/assignments/",
        {"user": delegate.pk, "scope": str(offering_a.pk), "role": "instructor"},
        format="json",
    )
    assert role_res.status_code == 201
    role_assignment_id = role_res.data["id"]

    grant_res = admin_client.post(
        "/api/access/assignments/",
        {"user": delegate.pk, "scope": str(offering_a.pk), "capability": "grades.edit"},
        format="json",
    )
    assert grant_res.status_code == 201
    grant_id = grant_res.data["id"]

    # Revoke the direct grant; instructor role still authorizes grades.edit
    assert admin_client.delete(f"/api/access/grants/{grant_id}/").status_code == 204
    assert delegate_client.get("/api/v1/workspaces/instructor/").status_code == 200
    grade_res = delegate_client.post(
        "/api/v1/grades/",
        {
            "enrollment": str(auth02_world["enrollment_a1"].pk),
            "assessment": str(auth02_world["assessment_a"].pk),
            "batch": str(auth02_world["batch_a"].pk),
            "state": "scored",
            "points_earned": "88.00",
        },
        format="json",
    )
    assert grade_res.status_code == 201, grade_res.data
    grade_id = grade_res.data["id"]

    # Now revoke the role assignment as well; access is removed immediately
    assert admin_client.delete(f"/api/access/roles/{role_assignment_id}/").status_code == 204
    assert delegate_client.get("/api/v1/workspaces/instructor/").status_code == 403
    assert delegate_client.get(f"/api/v1/grades/{grade_id}/").status_code == 404
    assert (
        delegate_client.patch(
            f"/api/v1/grades/{grade_id}/",
            {"expected_version": 1, "state": "scored", "points_earned": "90.00"},
            format="json",
        ).status_code
        == 404
    )

    # Scenario B: Re-grant both, then revoke the role first; direct grant preserves access
    role_res_2 = admin_client.post(
        "/api/access/assignments/",
        {"user": delegate.pk, "scope": str(offering_a.pk), "role": "instructor"},
        format="json",
    )
    assert role_res_2.status_code == 201
    role_id_2 = role_res_2.data["id"]

    grant_res_2 = admin_client.post(
        "/api/access/assignments/",
        {"user": delegate.pk, "scope": str(offering_a.pk), "capability": "grades.edit"},
        format="json",
    )
    assert grant_res_2.status_code == 201
    grant_id_2 = grant_res_2.data["id"]

    # Revoke role first
    assert admin_client.delete(f"/api/access/roles/{role_id_2}/").status_code == 204

    # Direct grant continues to authorize instructor workspace, offering, roster, and grade editing
    assert delegate_client.get("/api/v1/workspaces/instructor/").status_code == 200
    assert delegate_client.get(f"/api/v1/offerings/{offering_a.pk}/").status_code == 200
    patch_res = delegate_client.patch(
        f"/api/v1/grades/{grade_id}/",
        {"expected_version": 1, "state": "scored", "points_earned": "94.00"},
        format="json",
    )
    assert patch_res.status_code == 200, patch_res.data
    assert patch_res.data["version"] == 2

    # Finally revoke the direct grant; access is removed
    assert admin_client.delete(f"/api/access/grants/{grant_id_2}/").status_code == 204
    assert delegate_client.get("/api/v1/workspaces/instructor/").status_code == 403
    assert delegate_client.get(f"/api/v1/grades/{grade_id}/").status_code == 404


def test_auth02_unauthorized_grant_and_revoke_attempts(auth02_world):
    """4. Unauthenticated and unauthorized actors cannot list, create, or revoke capability grants."""
    admin = auth02_world["admin"]
    delegate = auth02_world["delegate"]
    instructor = auth02_world["instructor"]
    coordinator = auth02_world["coordinator"]
    student1 = auth02_world["student1"]
    outsider = auth02_world["outsider"]
    inst = auth02_world["inst"]
    offering_a = auth02_world["offering_a"]

    # Create a legitimate grant by admin so we can test unauthorized revocation attempts
    existing_grant = assign(
        actor=admin,
        user=delegate,
        scope=Scope.objects.get(pk=offering_a.pk),
        capability=Capability.objects.get(pk="grades.view"),
    )
    before_grant_count = DirectCapabilityGrant.objects.filter(revoked_at__isnull=True).count()
    before_audit_count = AuditEvent.objects.count()

    payload = {
        "user": outsider.pk,
        "scope": str(offering_a.pk),
        "capability": "grades.edit",
    }

    # Unauthenticated client gets 401/403
    anon_client = APIClient()
    assert anon_client.get(f"/api/access/dashboard/?scope={inst.pk}").status_code in (401, 403)
    assert anon_client.post("/api/access/assignments/", payload, format="json").status_code in (
        401,
        403,
    )
    assert anon_client.delete(f"/api/access/grants/{existing_grant.pk}/").status_code in (401, 403)

    # Authenticated users without access.manage (student, instructor, coordinator, outsider) are denied
    for unauthorized_user in (student1, instructor, coordinator, outsider):
        client = APIClient()
        client.force_authenticate(unauthorized_user)

        # Listing dashboard grants
        dash_res = client.get(f"/api/access/dashboard/?scope={inst.pk}")
        assert dash_res.status_code == 403

        # Creating a grant
        create_res = client.post("/api/access/assignments/", payload, format="json")
        assert create_res.status_code == 403

        # Revoking an existing grant outside administrable scopes returns 404
        revoke_res = client.delete(f"/api/access/grants/{existing_grant.pk}/")
        assert revoke_res.status_code in (403, 404)

    # Verify no database or audit records were mutated
    assert (
        DirectCapabilityGrant.objects.filter(revoked_at__isnull=True).count() == before_grant_count
    )
    assert AuditEvent.objects.count() == before_audit_count
    existing_grant.refresh_from_db()
    assert existing_grant.revoked_at is None


def test_auth02_audit_trail_verification(auth02_world):
    """5. Creating and revoking a direct capability grant records immutable AuditEvent entries."""
    admin = auth02_world["admin"]
    delegate = auth02_world["delegate"]
    offering_a = auth02_world["offering_a"]

    AuditEvent.objects.none()  # sanity check
    initial_event_ids = set(AuditEvent.objects.values_list("id", flat=True))

    admin_client = APIClient()
    admin_client.force_authenticate(admin)

    # Create direct grant
    create_res = admin_client.post(
        "/api/access/assignments/",
        {
            "user": delegate.pk,
            "scope": str(offering_a.pk),
            "capability": "grades.edit",
        },
        format="json",
    )
    assert create_res.status_code == 201
    grant_id = create_res.data["id"]

    grant_event = AuditEvent.objects.exclude(id__in=initial_event_ids).get()
    assert grant_event.action == "capability.granted"
    assert grant_event.actor_id == admin.pk
    assert grant_event.subject_id == delegate.pk
    assert grant_event.scope_id == offering_a.pk
    assert grant_event.metadata == {
        "assignment_id": grant_id,
        "role": None,
        "capability": "grades.edit",
    }

    # Revoke direct grant
    revoke_res = admin_client.delete(f"/api/access/grants/{grant_id}/")
    assert revoke_res.status_code == 204

    revoke_event = AuditEvent.objects.exclude(id__in=initial_event_ids | {grant_event.pk}).get()
    assert revoke_event.action == "capability.revoked"
    assert revoke_event.actor_id == admin.pk
    assert revoke_event.subject_id == delegate.pk
    assert revoke_event.scope_id == offering_a.pk
    assert revoke_event.metadata == {
        "assignment_id": grant_id,
    }


@pytest.mark.parametrize(
    "capability_code",
    [
        "grades.view",
        "grades.edit",
        "grades.release",
        "offering.manage",
        "syllabus.draft",
    ],
)
def test_auth02_all_offering_capabilities_unlock_workspace_and_offering_scoping(
    auth02_world, capability_code
):
    """Verify every offering capability in the instructor/offering set unlocks workspace & offering visibility."""
    admin = auth02_world["admin"]
    delegate = auth02_world["delegate"]
    offering_a = auth02_world["offering_a"]

    grant = assign(
        actor=admin,
        user=delegate,
        scope=Scope.objects.get(pk=offering_a.pk),
        capability=Capability.objects.get(pk=capability_code),
    )

    ws_svc = WorkspaceService(actor=delegate)
    assert list(ws_svc.instructor_offerings()) == [offering_a]

    off_svc = CourseOfferingService(actor=delegate)
    assert list(off_svc.get_queryset()) == [offering_a]

    enr_svc = EnrollmentService(actor=delegate)
    if capability_code in {"grades.view", "grades.edit", "grades.release", "offering.manage"}:
        assert enr_svc.get_queryset().count() == 2
    else:
        assert enr_svc.get_queryset().count() == 0

    revoke(actor=admin, assignment=grant)
    with pytest.raises(PermissionDenied, match="Instructor access is required."):
        ws_svc.instructor_offerings()
