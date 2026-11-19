import pytest
from access.models import Role, RoleAssignment, Scope
from access.policy import AuthorizationService
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.controllers.courses import CourseController
from academic.controllers.departments import DepartmentController
from academic.controllers.institutions import InstitutionController
from academic.controllers.terms import AcademicTermController
from academic.models import AcademicTerm, Course, Department, Institution
from academic.services.structure import (
    AcademicTermService,
    CourseService,
    DepartmentService,
    InstitutionService,
)


@pytest.fixture
def structure_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("struct_admin")
    guest = user_model.objects.create_user("struct_guest")
    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Test University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)
    inst = Institution.objects.create(pk=root.pk, code="TU", name="Test University")
    dept = Department.objects.create(institution=inst, code="CS", name="Computer Science")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CS101", title="Intro to CS", ects=6, credits=4
    )
    return {
        "admin": admin,
        "guest": guest,
        "root": root,
        "inst": inst,
        "dept": dept,
        "term": term,
        "course": course,
    }


def test_structure_services_registered_in_wireup():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        inst_svc = scoped.get(InstitutionService)
        assert isinstance(inst_svc, InstitutionService)
        assert isinstance(inst_svc.auth_service, AuthorizationService)

        dept_svc = scoped.get(DepartmentService)
        assert isinstance(dept_svc, DepartmentService)
        assert isinstance(dept_svc.auth_service, AuthorizationService)

        term_svc = scoped.get(AcademicTermService)
        assert isinstance(term_svc, AcademicTermService)
        assert isinstance(term_svc.auth_service, AuthorizationService)

        course_svc = scoped.get(CourseService)
        assert isinstance(course_svc, CourseService)
        assert isinstance(course_svc.auth_service, AuthorizationService)


def test_institution_service_constructor_injection(structure_world):
    auth_service = AuthorizationService()
    svc = InstitutionService(auth_service=auth_service)
    qs = svc.get_queryset(actor=structure_world["admin"])
    assert qs.filter(code="TU").exists()

    guest_qs = svc.get_queryset(actor=structure_world["guest"])
    assert not guest_qs.filter(code="TU").exists()


def test_department_service_mutations(structure_world):
    auth_service = AuthorizationService()
    svc = DepartmentService(auth_service=auth_service)

    dept = svc.create(
        institution=structure_world["inst"],
        code="MATH",
        name="Mathematics",
    )
    assert dept.pk is not None
    assert dept.code == "MATH"

    # Immutability check
    with pytest.raises(ValidationError):
        other_root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Other U")
        other_inst = Institution.objects.create(pk=other_root.pk, code="OU", name="Other U")
        svc.update(instance=dept, institution=other_inst)


def test_academic_term_service_date_validation(structure_world):
    auth_service = AuthorizationService()
    svc = AcademicTermService(auth_service=auth_service)

    with pytest.raises(ValidationError) as exc:
        svc.create(
            institution=structure_world["inst"],
            year=2027,
            season="spring",
            starts_at="2027-06-01",
            ends_at="2027-01-01",  # Invalid: ends before starts
        )
    assert "ends_at" in exc.value.message_dict


def test_controller_guard_enforcement(structure_world):
    from rest_framework.test import APIRequestFactory

    rf = APIRequestFactory()

    # 1. Department create guard check via as_view (scope_field="institution")
    view_dept = DepartmentController.as_view({"post": "create"})
    req_guest = rf.post(
        "/api/v1/departments/",
        {"institution": str(structure_world["inst"].pk), "code": "PHYS", "name": "Physics"},
        format="json",
    )
    req_guest.user = structure_world["guest"]
    assert view_dept(req_guest).status_code == 403

    req_admin = rf.post(
        "/api/v1/departments/",
        {"institution": str(structure_world["inst"].pk), "code": "PHYS", "name": "Physics"},
        format="json",
    )
    req_admin.user = structure_world["admin"]
    assert view_dept(req_admin).status_code == 201

    # 2. Course create guard check (scope_field="home_department.institution")
    view_course = CourseController.as_view({"post": "create"})
    course_req_guest = rf.post(
        "/api/v1/courses/",
        {
            "home_department": str(structure_world["dept"].pk),
            "code": "CS102",
            "title": "Data Structures",
            "ects": 6,
            "credits": 4,
        },
        format="json",
    )
    course_req_guest.user = structure_world["guest"]
    assert view_course(course_req_guest).status_code == 403

    course_req_admin = rf.post(
        "/api/v1/courses/",
        {
            "home_department": str(structure_world["dept"].pk),
            "code": "CS102",
            "title": "Data Structures",
            "ects": 6,
            "credits": 4,
        },
        format="json",
    )
    course_req_admin.user = structure_world["admin"]
    res_course = view_course(course_req_admin)
    assert res_course.status_code == 201

    # 3. Course update guard check (detail action with scope_field="home_department.institution")
    view_course_update = CourseController.as_view({"patch": "partial_update"})
    update_req_guest = rf.patch(
        f"/api/v1/courses/{structure_world['course'].pk}/",
        {"title": "Updated Title"},
        format="json",
    )
    update_req_guest.user = structure_world["guest"]
    assert view_course_update(
        update_req_guest, pk=str(structure_world["course"].pk)
    ).status_code in (403, 404)

    update_req_admin = rf.patch(
        f"/api/v1/courses/{structure_world['course'].pk}/",
        {"title": "Updated Title"},
        format="json",
    )
    update_req_admin.user = structure_world["admin"]
    assert (
        view_course_update(update_req_admin, pk=str(structure_world["course"].pk)).status_code
        == 200
    )

    # 4. Institution create guard check (scope_field="name")
    new_scope = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="New University")
    RoleAssignment.objects.create(
        user=structure_world["admin"],
        role=Role.objects.get(pk="administrator"),
        scope=new_scope,
    )
    view_inst = InstitutionController.as_view({"post": "create"})
    inst_req_guest = rf.post(
        "/api/v1/institutions/",
        {"code": "NU", "name": "New University"},
        format="json",
    )
    inst_req_guest.user = structure_world["guest"]
    assert view_inst(inst_req_guest).status_code == 403

    inst_req_admin = rf.post(
        "/api/v1/institutions/",
        {"code": "NU", "name": "New University"},
        format="json",
    )
    inst_req_admin.user = structure_world["admin"]
    assert view_inst(inst_req_admin).status_code == 201


def test_controllers_accept_injected_services():
    mock_inst_svc = InstitutionService(auth_service=AuthorizationService())
    c1 = InstitutionController(service=mock_inst_svc)
    assert c1.service is mock_inst_svc

    mock_dept_svc = DepartmentService(auth_service=AuthorizationService())
    c2 = DepartmentController(service=mock_dept_svc)
    assert c2.service is mock_dept_svc

    mock_term_svc = AcademicTermService(auth_service=AuthorizationService())
    c3 = AcademicTermController(service=mock_term_svc)
    assert c3.service is mock_term_svc

    mock_course_svc = CourseService(auth_service=AuthorizationService())
    c4 = CourseController(service=mock_course_svc)
    assert c4.service is mock_course_svc
