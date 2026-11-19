import pytest
from access.models import DirectCapabilityGrant, Role, RoleAssignment, Scope
from access.policy import AuthorizationService
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from rest_framework.test import APIClient, APIRequestFactory
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.controllers.workspaces import (
    CoordinatorWorkspaceController,
    InstructorWorkspaceController,
    StudentWorkspaceController,
)
from academic.models import (
    AcademicTerm,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Institution,
    Program,
    ProgramCourse,
    ProgramMembership,
)
from academic.services.workspaces import WorkspaceService


def grant_role(user, scope_id, role_slug):
    return RoleAssignment.objects.get_or_create(
        user=user, scope_id=scope_id, role_id=role_slug, revoked_at__isnull=True
    )[0]


@pytest.fixture
def workspace_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("ws_admin")
    coordinator = user_model.objects.create_user("ws_coord")
    instructor = user_model.objects.create_user("ws_instructor")
    student1 = user_model.objects.create_user(
        "ws_student1", first_name="Alice", last_name="Smith", email="alice@example.com"
    )
    student2 = user_model.objects.create_user(
        "ws_student2", first_name="Bob", last_name="Jones", email="bob@example.com"
    )
    guest = user_model.objects.create_user("ws_guest")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Workspace University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="WU", name="Workspace University")
    dept = Department.objects.create(institution=inst, code="CS", name="Computer Science")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course_a = Course.objects.create(
        home_department=dept, code="CS101", title="Introduction to CS", ects=6, credits=4
    )
    course_b = Course.objects.create(
        home_department=dept, code="CS201", title="Data Structures", ects=6, credits=4
    )

    program_a = Program.objects.create(
        department=dept,
        code="CS-BS",
        title="B.S. Computer Science",
        status=Program.Status.ACTIVE,
    )
    program_b = Program.objects.create(
        department=dept,
        code="CS-MS",
        title="M.S. Computer Science",
        status=Program.Status.ACTIVE,
    )

    ProgramCourse.objects.create(
        program=program_a,
        course=course_a,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2026-01-01",
    )
    ProgramCourse.objects.create(
        program=program_b,
        course=course_b,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2026-01-01",
    )

    offering_a = CourseOffering.objects.create(
        program=program_a,
        course=course_a,
        term=term,
        section="01",
        status=CourseOffering.Status.ACTIVE,
    )
    offering_b = CourseOffering.objects.create(
        program=program_b,
        course=course_b,
        term=term,
        section="01",
        status=CourseOffering.Status.ACTIVE,
    )

    # Program memberships
    pm1 = ProgramMembership.objects.create(
        program=program_a,
        user=student1,
        student_number="S001",
        status=ProgramMembership.Status.ACTIVE,
    )
    pm2 = ProgramMembership.objects.create(
        program=program_a,
        user=student2,
        student_number="S002",
        status=ProgramMembership.Status.ACTIVE,
    )

    # Coordinator role on program_a only
    grant_role(coordinator, program_a.pk, "program-coordinator")

    # Instructor role on offering_a only
    grant_role(instructor, offering_a.pk, "instructor")

    # Student roles on offering_a
    grant_role(student1, offering_a.pk, "student")
    grant_role(student2, offering_a.pk, "student")

    # Enrollments
    enr1 = Enrollment.objects.create(
        offering=offering_a, student=student1, status=Enrollment.Status.ENROLLED
    )
    enr2 = Enrollment.objects.create(
        offering=offering_a, student=student2, status=Enrollment.Status.ENROLLED
    )

    return {
        "admin": admin,
        "coordinator": coordinator,
        "instructor": instructor,
        "student1": student1,
        "student2": student2,
        "guest": guest,
        "inst": inst,
        "dept": dept,
        "term": term,
        "program_a": program_a,
        "program_b": program_b,
        "offering_a": offering_a,
        "offering_b": offering_b,
        "membership1": pm1,
        "membership2": pm2,
        "enrollment1": enr1,
        "enrollment2": enr2,
    }


def test_workspace_service_registered_in_wireup():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        svc = scoped.get(WorkspaceService)
        assert isinstance(svc, WorkspaceService)
        assert isinstance(svc.auth_service, AuthorizationService)


def test_workspace_service_constructor_injection():
    mock_auth = AuthorizationService()
    svc = WorkspaceService(auth_service=mock_auth, actor="dummy-actor")
    assert svc.auth_service is mock_auth
    assert svc.actor == "dummy-actor"

    svc_default = WorkspaceService()
    assert isinstance(svc_default.auth_service, AuthorizationService)
    assert svc_default.actor is None


def test_controllers_constructor_injection():
    ctrl_inst = InstructorWorkspaceController()
    assert isinstance(ctrl_inst.service, WorkspaceService)

    ctrl_stud = StudentWorkspaceController()
    assert isinstance(ctrl_stud.service, WorkspaceService)

    ctrl_coord = CoordinatorWorkspaceController()
    assert isinstance(ctrl_coord.service, WorkspaceService)

    # Test explicit custom service injection
    custom_svc = WorkspaceService()
    ctrl_inst_custom = InstructorWorkspaceController(service=custom_svc)
    assert ctrl_inst_custom.service is custom_svc

    ctrl_stud_custom = StudentWorkspaceController(service=custom_svc)
    assert ctrl_stud_custom.service is custom_svc

    ctrl_coord_custom = CoordinatorWorkspaceController(service=custom_svc)
    assert ctrl_coord_custom.service is custom_svc


def test_controllers_finalize_response_cache_control():
    rf = APIRequestFactory()
    request = rf.get("/api/v1/workspaces/instructor/")

    for ctrl_cls in (
        InstructorWorkspaceController,
        StudentWorkspaceController,
        CoordinatorWorkspaceController,
    ):
        ctrl = ctrl_cls()
        ctrl.headers = {}
        response = HttpResponse()
        finalized = ctrl.finalize_response(request, response)
        assert finalized["Cache-Control"] == "no-store"


def test_instructor_workspace_scoping_and_permissions(workspace_world):
    instructor = workspace_world["instructor"]
    guest = workspace_world["guest"]
    offering_a = workspace_world["offering_a"]
    offering_b = workspace_world["offering_b"]

    svc = WorkspaceService(actor=instructor)
    offerings = list(svc.instructor_offerings())
    assert len(offerings) == 1
    assert offerings[0].pk == offering_a.pk

    roster = list(svc.instructor_roster(offering_a))
    assert len(roster) == 2
    student_usernames = {enr.student.username for enr in roster}
    assert student_usernames == {"ws_student1", "ws_student2"}

    # Direct Capability Grant path: grant grades.view capability on offering_b
    DirectCapabilityGrant.objects.create(
        user=instructor, capability_id="grades.view", scope=Scope.objects.get(pk=offering_b.pk)
    )
    expanded_offerings = list(svc.instructor_offerings())
    assert len(expanded_offerings) == 2
    assert {o.pk for o in expanded_offerings} == {offering_a.pk, offering_b.pk}

    # Unauthorized actor raises PermissionDenied
    guest_svc = WorkspaceService(actor=guest)
    with pytest.raises(PermissionDenied, match="Instructor access is required."):
        guest_svc.instructor_offerings()

    # Via APIClient
    client = APIClient()
    client.force_authenticate(instructor)
    res = client.get("/api/v1/workspaces/instructor/")
    assert res.status_code == 200
    assert res["Cache-Control"] == "no-store"
    assert any(item["id"] == str(offering_a.pk) for item in res.data["offerings"])

    client.force_authenticate(guest)
    res_guest = client.get("/api/v1/workspaces/instructor/")
    assert res_guest.status_code == 403


def test_student_workspace_scoping_and_permissions(workspace_world):
    student1 = workspace_world["student1"]
    student2 = workspace_world["student2"]
    guest = workspace_world["guest"]
    offering_a = workspace_world["offering_a"]

    svc1 = WorkspaceService(actor=student1)
    enrs1 = list(svc1.student_enrollments())
    assert len(enrs1) == 1
    assert enrs1[0].offering_id == offering_a.pk
    assert enrs1[0].student_id == student1.pk

    svc2 = WorkspaceService(actor=student2)
    enrs2 = list(svc2.student_enrollments())
    assert len(enrs2) == 1
    assert enrs2[0].student_id == student2.pk

    guest_svc = WorkspaceService(actor=guest)
    with pytest.raises(PermissionDenied, match="Student access is required."):
        guest_svc.student_enrollments()

    # Via APIClient
    client = APIClient()
    client.force_authenticate(student1)
    res = client.get("/api/v1/workspaces/student/")
    assert res.status_code == 200
    assert res["Cache-Control"] == "no-store"
    assert len(res.data["courses"]) == 1
    assert res.data["courses"][0]["enrollment_id"] == str(workspace_world["enrollment1"].pk)
    assert res.data["outcomes"] == []

    client.force_authenticate(guest)
    res_guest = client.get("/api/v1/workspaces/student/")
    assert res_guest.status_code == 403


def test_coordinator_workspace_scoping_and_permissions(workspace_world):
    coordinator = workspace_world["coordinator"]
    guest = workspace_world["guest"]
    program_a = workspace_world["program_a"]
    program_b = workspace_world["program_b"]
    offering_a = workspace_world["offering_a"]

    svc = WorkspaceService(actor=coordinator)
    programs = list(svc.coordinator_programs())
    assert len(programs) == 1
    assert programs[0].pk == program_a.pk
    assert program_b.pk not in [p.pk for p in programs]

    offerings = list(svc.coordinator_offerings(programs))
    assert len(offerings) == 1
    assert offerings[0].pk == offering_a.pk

    memberships = list(svc.coordinator_memberships(programs))
    assert len(memberships) == 2
    student_numbers = {m.student_number for m in memberships}
    assert student_numbers == {"S001", "S002"}

    guest_svc = WorkspaceService(actor=guest)
    with pytest.raises(PermissionDenied, match="Program coordinator access is required."):
        guest_svc.coordinator_programs()

    # Via APIClient
    client = APIClient()
    client.force_authenticate(coordinator)
    res = client.get("/api/v1/workspaces/coordinator/")
    assert res.status_code == 200
    assert res["Cache-Control"] == "no-store"
    assert [p["id"] for p in res.data["programs"]] == [str(program_a.pk)]
    assert [o["id"] for o in res.data["offerings"]] == [str(offering_a.pk)]
    assert len(res.data["students"]) == 2

    client.force_authenticate(guest)
    res_guest = client.get("/api/v1/workspaces/coordinator/")
    assert res_guest.status_code == 403


def test_workspace_service_actor_override(workspace_world):
    guest = workspace_world["guest"]
    instructor = workspace_world["instructor"]
    student = workspace_world["student1"]
    coordinator = workspace_world["coordinator"]

    svc = WorkspaceService(actor=guest)
    # Passing explicit actor overrides self.actor
    offerings = list(svc.instructor_offerings(actor=instructor))
    assert len(offerings) == 1

    enrollments = list(svc.student_enrollments(actor=student))
    assert len(enrollments) == 1

    programs = list(svc.coordinator_programs(actor=coordinator))
    assert len(programs) == 1


def test_workspace_service_membership_user_data(workspace_world):
    pm = workspace_world["membership1"]
    data = WorkspaceService.membership_user_data(pm)
    assert data["program_id"] == str(workspace_world["program_a"].pk)
    assert data["student_number"] == "S001"
    assert data["membership_status"] == ProgramMembership.Status.ACTIVE
    assert data["username"] == "ws_student1"
    assert data["first_name"] == "Alice"
    assert data["last_name"] == "Smith"
    assert data["email"] == "alice@example.com"
