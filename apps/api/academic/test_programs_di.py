import pytest
from access.models import Role, RoleAssignment, Scope
from access.policy import AuthorizationService
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.controllers.program_courses import ProgramCourseController
from academic.controllers.program_memberships import ProgramMembershipController
from academic.controllers.programs import ProgramController
from academic.models import (
    AcademicTerm,
    Course,
    Department,
    Institution,
    Program,
    ProgramMembership,
)
from academic.services.programs import (
    ProgramCourseService,
    ProgramMembershipService,
    ProgramService,
)


@pytest.fixture
def program_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("prog_admin")
    guest = user_model.objects.create_user("prog_guest")
    student = user_model.objects.create_user("prog_student")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Program University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="PU", name="Program University")
    dept = Department.objects.create(institution=inst, code="CS", name="Computer Science")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CS201", title="Algorithms", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CS-BS",
        title="B.S. in Computer Science",
        status=Program.Status.ACTIVE,
    )
    return {
        "admin": admin,
        "guest": guest,
        "student": student,
        "root": root,
        "inst": inst,
        "dept": dept,
        "term": term,
        "course": course,
        "program": program,
    }


def test_program_services_registered_in_wireup():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        prog_svc = scoped.get(ProgramService)
        assert isinstance(prog_svc, ProgramService)
        assert isinstance(prog_svc.auth_service, AuthorizationService)

        pc_svc = scoped.get(ProgramCourseService)
        assert isinstance(pc_svc, ProgramCourseService)
        assert isinstance(pc_svc.auth_service, AuthorizationService)

        pm_svc = scoped.get(ProgramMembershipService)
        assert isinstance(pm_svc, ProgramMembershipService)
        assert isinstance(pm_svc.auth_service, AuthorizationService)


def test_program_service_constructor_injection_and_scoping(program_world):
    auth_service = AuthorizationService()
    svc = ProgramService(auth_service=auth_service)

    admin_qs = svc.get_queryset(actor=program_world["admin"])
    assert admin_qs.filter(code="CS-BS").exists()

    guest_qs = svc.get_queryset(actor=program_world["guest"])
    assert not guest_qs.filter(code="CS-BS").exists()


def test_program_service_mutations_and_immutability(program_world):
    auth_service = AuthorizationService()
    svc = ProgramService(auth_service=auth_service)

    new_prog = svc.create(
        department=program_world["dept"],
        code="CS-MS",
        title="M.S. in Computer Science",
        status=Program.Status.ACTIVE,
    )
    assert new_prog.pk is not None
    assert new_prog.code == "CS-MS"

    # Immutability check on department
    with pytest.raises(ValidationError):
        other_dept = Department.objects.create(
            institution=program_world["inst"], code="MATH", name="Mathematics"
        )
        svc.update(instance=new_prog, department=other_dept)


def test_program_course_service_window_validation_and_immutability(program_world):
    auth_service = AuthorizationService()
    svc = ProgramCourseService(auth_service=auth_service)

    # Invalid window: effective_to < effective_from
    with pytest.raises(ValidationError) as exc:
        svc.create(
            program=program_world["program"],
            course=program_world["course"],
            effective_from="2026-09-01",
            effective_to="2026-06-01",
        )
    assert "effective_to" in exc.value.message_dict

    # Valid link
    pc = svc.create(
        program=program_world["program"],
        course=program_world["course"],
        effective_from="2026-09-01",
        effective_to="2027-09-01",
    )
    assert pc.pk is not None

    # Immutability check on course
    with pytest.raises(ValidationError):
        other_course = Course.objects.create(
            home_department=program_world["dept"],
            code="CS202",
            title="Operating Systems",
            ects=6,
            credits=4,
        )
        svc.update(instance=pc, course=other_course)


def test_program_membership_service_mutations_and_immutability(program_world):
    auth_service = AuthorizationService()
    svc = ProgramMembershipService(auth_service=auth_service)

    pm = svc.create(
        program=program_world["program"],
        user=program_world["student"],
        student_number="S12345",
        status=ProgramMembership.Status.ACTIVE,
    )
    assert pm.pk is not None
    assert pm.student_number == "S12345"

    # Immutability check on user
    with pytest.raises(ValidationError):
        svc.update(instance=pm, user=program_world["admin"])


def test_program_controllers_guard_enforcement(program_world):
    from rest_framework.test import APIRequestFactory

    rf = APIRequestFactory()

    # 1. Program create: scope_field="department.institution"
    view_prog = ProgramController.as_view({"post": "create"})
    guest_prog_req = rf.post(
        "/api/v1/programs/",
        {
            "department": str(program_world["dept"].pk),
            "code": "BIO-BS",
            "title": "B.S. in Biology",
        },
        format="json",
    )
    guest_prog_req.user = program_world["guest"]
    assert view_prog(guest_prog_req).status_code == 403

    admin_prog_req = rf.post(
        "/api/v1/programs/",
        {
            "department": str(program_world["dept"].pk),
            "code": "BIO-BS",
            "title": "B.S. in Biology",
        },
        format="json",
    )
    admin_prog_req.user = program_world["admin"]
    assert view_prog(admin_prog_req).status_code == 201

    # 2. ProgramCourse create: scope_field="program"
    view_pc = ProgramCourseController.as_view({"post": "create"})
    guest_pc_req = rf.post(
        "/api/v1/program-courses/",
        {
            "program": str(program_world["program"].pk),
            "course": str(program_world["course"].pk),
            "effective_from": "2026-09-01",
        },
        format="json",
    )
    guest_pc_req.user = program_world["guest"]
    assert view_pc(guest_pc_req).status_code == 403

    admin_pc_req = rf.post(
        "/api/v1/program-courses/",
        {
            "program": str(program_world["program"].pk),
            "course": str(program_world["course"].pk),
            "effective_from": "2026-09-01",
        },
        format="json",
    )
    admin_pc_req.user = program_world["admin"]
    assert view_pc(admin_pc_req).status_code == 201

    # 3. ProgramMembership create: scope_field="program"
    view_pm = ProgramMembershipController.as_view({"post": "create"})
    guest_pm_req = rf.post(
        "/api/v1/program-memberships/",
        {
            "program": str(program_world["program"].pk),
            "user": program_world["student"].pk,
            "student_number": "STU-001",
        },
        format="json",
    )
    guest_pm_req.user = program_world["guest"]
    assert view_pm(guest_pm_req).status_code == 403

    admin_pm_req = rf.post(
        "/api/v1/program-memberships/",
        {
            "program": str(program_world["program"].pk),
            "user": program_world["student"].pk,
            "student_number": "STU-001",
        },
        format="json",
    )
    admin_pm_req.user = program_world["admin"]
    assert view_pm(admin_pm_req).status_code == 201


def test_controllers_accept_injected_services():
    auth_service = AuthorizationService()

    mock_prog_svc = ProgramService(auth_service=auth_service)
    c1 = ProgramController(service=mock_prog_svc)
    assert c1.service is mock_prog_svc

    mock_pc_svc = ProgramCourseService(auth_service=auth_service)
    c2 = ProgramCourseController(service=mock_pc_svc)
    assert c2.service is mock_pc_svc

    mock_pm_svc = ProgramMembershipService(auth_service=auth_service)
    c3 = ProgramMembershipController(service=mock_pm_svc)
    assert c3.service is mock_pm_svc
