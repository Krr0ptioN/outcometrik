import datetime as dt
from decimal import Decimal

import pytest
from access.models import Role, RoleAssignment, Scope
from access.policy import AuthorizationService
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.controllers.assessments import AssessmentController
from academic.controllers.syllabi import SyllabusController
from academic.models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Institution,
    Program,
    ProgramCourse,
    ProgramOutcomeSet,
    Syllabus,
    SyllabusAssessment,
)
from academic.services.assessments import AssessmentService
from academic.services.offerings import InstructorAssignmentService
from academic.services.syllabi import SyllabusService


@pytest.fixture
def syllabi_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("syl_admin")
    guest = user_model.objects.create_user("syl_guest")
    teacher = user_model.objects.create_user("syl_teacher")
    coord = user_model.objects.create_user("syl_coord")
    student = user_model.objects.create_user("syl_student")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Syllabi University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="SU", name="Syllabi University")
    dept = Department.objects.create(institution=inst, code="CS", name="Computer Science")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CS301", title="Databases", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CS-BS",
        title="B.S. in Computer Science",
        status=Program.Status.ACTIVE,
    )
    prog_course = ProgramCourse.objects.create(
        program=program,
        course=course,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2026-01-01",
    )
    po_set = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        source_reference="docs/ref",
        status=ProgramOutcomeSet.Status.ACTIVE,
        effective_date=dt.date(2026, 1, 1),
        activated_at=dt.datetime.now(dt.UTC),
        activated_by=admin,
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

    RoleAssignment.objects.create(user=coord, scope_id=program.pk, role_id="program-coordinator")
    InstructorAssignmentService(actor=admin).create(
        offering=offering, user=teacher, assignment_role="instructor"
    )
    RoleAssignment.objects.create(user=student, scope_id=offering.pk, role_id="student")

    assessment = Assessment.objects.create(
        offering=offering,
        title="Midterm Exam",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )

    return {
        "admin": admin,
        "guest": guest,
        "teacher": teacher,
        "coord": coord,
        "student": student,
        "inst": inst,
        "dept": dept,
        "term": term,
        "course": course,
        "program": program,
        "prog_course": prog_course,
        "po_set": po_set,
        "offering": offering,
        "other_offering": other_offering,
        "assessment": assessment,
    }


def test_syllabi_and_assessments_services_registered_in_wireup():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        s_svc = scoped.get(SyllabusService)
        assert isinstance(s_svc, SyllabusService)
        assert isinstance(s_svc.auth_service, AuthorizationService)

        a_svc = scoped.get(AssessmentService)
        assert isinstance(a_svc, AssessmentService)
        assert isinstance(a_svc.auth_service, AuthorizationService)


def test_syllabi_services_constructor_injection_and_scoping(syllabi_world):
    auth_service = AuthorizationService()
    s_svc = SyllabusService(auth_service=auth_service)
    a_svc = AssessmentService(auth_service=auth_service)

    draft = s_svc.create(offering=syllabi_world["offering"])

    assert s_svc.get_queryset(actor=syllabi_world["admin"]).filter(pk=draft.pk).exists()
    assert s_svc.get_queryset(actor=syllabi_world["teacher"]).filter(pk=draft.pk).exists()

    assert not s_svc.get_queryset(actor=syllabi_world["guest"]).filter(pk=draft.pk).exists()
    assert not s_svc.get_queryset(actor=syllabi_world["student"]).filter(pk=draft.pk).exists()

    assert (
        a_svc.get_queryset(actor=syllabi_world["admin"])
        .filter(pk=syllabi_world["assessment"].pk)
        .exists()
    )
    assert (
        a_svc.get_queryset(actor=syllabi_world["teacher"])
        .filter(pk=syllabi_world["assessment"].pk)
        .exists()
    )
    assert (
        not a_svc.get_queryset(actor=syllabi_world["guest"])
        .filter(pk=syllabi_world["assessment"].pk)
        .exists()
    )
    assert (
        not a_svc.get_queryset(actor=syllabi_world["student"])
        .filter(pk=syllabi_world["assessment"].pk)
        .exists()
    )


def test_syllabi_mutations_and_immutability(syllabi_world):
    auth_service = AuthorizationService()
    s_svc = SyllabusService(auth_service=auth_service)

    draft = s_svc.create(offering=syllabi_world["offering"])

    with pytest.raises(ValidationError):
        s_svc.update(instance=draft, offering=syllabi_world["other_offering"])

    with pytest.raises(ValidationError):
        s_svc.update(instance=draft, version=42)

    with pytest.raises(ValidationError):
        s_svc.update(instance=draft, status=Syllabus.Status.APPROVED)


def test_syllabi_lifecycle_transitions(syllabi_world):
    s_svc = SyllabusService()
    offering = syllabi_world["offering"]
    coord = syllabi_world["coord"]

    draft = s_svc.create(offering=offering)
    assert draft.status == Syllabus.Status.DRAFT
    assert draft.version == 1
    assert draft.po_set_version == syllabi_world["po_set"].version

    lo = s_svc.add_learning_outcome(
        syllabus=draft, code="LO1", description="Understand relational models", order=1
    )
    assert lo.pk is not None
    assert lo.code == "LO1"

    lo = s_svc.update_learning_outcome(instance=lo, description="Relational modeling updated")
    assert lo.description == "Relational modeling updated"

    asmt = s_svc.add_assessment(
        syllabus=draft,
        code="Q1",
        kind=SyllabusAssessment.Kind.QUIZ,
        order=1,
        max_points=Decimal("20.00"),
    )
    assert asmt.pk is not None
    asmt = s_svc.update_assessment(instance=asmt, max_points=Decimal("25.00"))
    assert asmt.max_points == Decimal("25.00")

    approved = s_svc.approve(syllabus=draft, actor=coord)
    assert approved.status == Syllabus.Status.APPROVED
    assert approved.approved_by == coord
    assert approved.approved_at is not None

    revision = s_svc.revise(syllabus=approved)
    assert revision.status == Syllabus.Status.DRAFT
    assert revision.version == 2
    assert revision.learning_outcomes.count() == 1
    assert revision.assessments.count() == 1

    approved_rev = s_svc.approve(syllabus=revision, actor=coord)
    assert approved_rev.status == Syllabus.Status.APPROVED
    approved.refresh_from_db()
    assert approved.status == Syllabus.Status.RETIRED

    draft_other = Syllabus.objects.create(
        offering=syllabi_world["other_offering"],
        version=1,
        status=Syllabus.Status.DRAFT,
        po_set_version=None,
    )
    bound = s_svc.bind_active_po_set(syllabus=draft_other)
    assert bound.po_set_version == syllabi_world["po_set"].version

    retired = s_svc.remove_unused_draft(syllabus=draft_other)
    assert retired.status == Syllabus.Status.RETIRED


def test_controllers_constructor_injection():
    s_ctrl = SyllabusController()
    assert isinstance(s_ctrl.service, SyllabusService)

    a_ctrl = AssessmentController()
    assert isinstance(a_ctrl.service, AssessmentService)


def test_syllabi_controller_guard_enforcement(syllabi_world):
    client = APIClient()

    client.force_authenticate(syllabi_world["guest"])
    res = client.post(
        "/api/v1/syllabi/",
        {"offering": str(syllabi_world["offering"].pk)},
        format="json",
    )
    assert res.status_code == 403

    client.force_authenticate(syllabi_world["teacher"])
    res = client.post(
        "/api/v1/syllabi/",
        {"offering": str(syllabi_world["offering"].pk)},
        format="json",
    )
    assert res.status_code == 201
    s_id = res.data["id"]

    res_approve = client.post(f"/api/v1/syllabi/{s_id}/approve/")
    assert res_approve.status_code == 403

    res_lo = client.post(
        f"/api/v1/syllabi/{s_id}/learning-outcomes/",
        {"code": "LO-CTRL", "description": "Controller guard test", "order": 1},
        format="json",
    )
    assert res_lo.status_code == 201
    lo_id = res_lo.data["id"]

    res_asmt = client.post(
        f"/api/v1/syllabi/{s_id}/assessments/",
        {"code": "A-CTRL", "kind": "exam", "order": 1, "max_points": "50.00"},
        format="json",
    )
    assert res_asmt.status_code == 201
    asmt_id = res_asmt.data["id"]

    client.force_authenticate(syllabi_world["guest"])
    assert client.patch(
        f"/api/v1/syllabi/{s_id}/learning-outcomes/{lo_id}/",
        {"description": "hack"},
        format="json",
    ).status_code in (403, 404)
    assert client.delete(f"/api/v1/syllabi/{s_id}/assessments/{asmt_id}/").status_code in (403, 404)

    client.force_authenticate(syllabi_world["coord"])
    res_coord_approve = client.post(f"/api/v1/syllabi/{s_id}/approve/")
    assert res_coord_approve.status_code == 200
    assert res_coord_approve.data["status"] == "approved"

    client.force_authenticate(syllabi_world["student"])
    res_student = client.get(f"/api/v1/syllabi/{s_id}/")
    assert res_student.status_code == 200
