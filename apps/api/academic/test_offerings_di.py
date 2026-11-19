import pytest
from access.models import Role, RoleAssignment, Scope
from access.policy import AuthorizationService
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.controllers.enrollments import EnrollmentController
from academic.controllers.instructor_assignments import InstructorAssignmentController
from academic.controllers.offerings import CourseOfferingController
from academic.models import (
    AcademicTerm,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Institution,
    InstructorAssignment,
    Program,
    ProgramCourse,
    ProgramMembership,
)
from academic.services.enrollments import EnrollmentService
from academic.services.offerings import (
    CourseOfferingService,
    InstructorAssignmentService,
)


@pytest.fixture
def offering_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("off_admin")
    guest = user_model.objects.create_user("off_guest")
    teacher = user_model.objects.create_user("off_teacher")
    student = user_model.objects.create_user("off_student")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Offering University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="OU", name="Offering University")
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
    offering = CourseOffering.objects.create(
        program=program,
        course=course,
        term=term,
        section="01",
        status=CourseOffering.Status.ACTIVE,
    )
    ProgramMembership.objects.create(
        program=program,
        user=student,
        student_number="S123",
        status=ProgramMembership.Status.ACTIVE,
    )
    RoleAssignment.objects.create(
        user=student,
        scope=Scope.objects.get(pk=offering.pk),
        role=Role.objects.get(pk="student"),
    )

    return {
        "admin": admin,
        "guest": guest,
        "teacher": teacher,
        "student": student,
        "root": root,
        "inst": inst,
        "dept": dept,
        "term": term,
        "course": course,
        "program": program,
        "prog_course": prog_course,
        "offering": offering,
    }


def test_offerings_services_registered_in_wireup():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        off_svc = scoped.get(CourseOfferingService)
        assert isinstance(off_svc, CourseOfferingService)
        assert isinstance(off_svc.auth_service, AuthorizationService)

        ia_svc = scoped.get(InstructorAssignmentService)
        assert isinstance(ia_svc, InstructorAssignmentService)
        assert isinstance(ia_svc.auth_service, AuthorizationService)

        enr_svc = scoped.get(EnrollmentService)
        assert isinstance(enr_svc, EnrollmentService)
        assert isinstance(enr_svc.auth_service, AuthorizationService)


def test_course_offering_service_constructor_injection_and_scoping(offering_world):
    auth_service = AuthorizationService()
    svc = CourseOfferingService(auth_service=auth_service)

    admin_qs = svc.get_queryset(actor=offering_world["admin"])
    assert admin_qs.filter(pk=offering_world["offering"].pk).exists()

    guest_qs = svc.get_queryset(actor=offering_world["guest"])
    assert not guest_qs.filter(pk=offering_world["offering"].pk).exists()


def test_course_offering_mutations_and_immutability(offering_world):
    auth_service = AuthorizationService()
    svc = CourseOfferingService(auth_service=auth_service)

    new_offering = svc.create(
        program=offering_world["program"],
        course=offering_world["course"],
        term=offering_world["term"],
        section="02",
    )
    assert new_offering.pk is not None
    assert new_offering.section == "02"

    with pytest.raises(ValidationError):
        svc.create(
            program=offering_world["program"],
            course=offering_world["course"],
            term=offering_world["term"],
            section="02",
        )

    updated = svc.update(instance=new_offering, status=CourseOffering.Status.ARCHIVED)
    assert updated.status == CourseOffering.Status.ARCHIVED

    with pytest.raises(ValidationError):
        svc.update(instance=new_offering, section="03", course=None)


def test_instructor_assignment_service_mutations(offering_world):
    auth_service = AuthorizationService()
    svc = InstructorAssignmentService(auth_service=auth_service)

    assignment = svc.create(
        offering=offering_world["offering"],
        user=offering_world["teacher"],
        assignment_role=InstructorAssignment.Role.INSTRUCTOR,
        actor=offering_world["admin"],
    )
    assert assignment.pk is not None
    assert assignment.assignment_role == InstructorAssignment.Role.INSTRUCTOR

    # Assigned instructor now has role assignment
    ra = RoleAssignment.objects.filter(
        user=offering_world["teacher"],
        scope_id=offering_world["offering"].pk,
        role_id="instructor",
    ).first()
    assert ra is not None

    # Immutability
    with pytest.raises(ValidationError):
        svc.update(instance=assignment, user=offering_world["guest"])


def test_enrollment_service_mutations_and_status(offering_world):
    auth_service = AuthorizationService()
    svc = EnrollmentService(auth_service=auth_service)

    enrollment = svc.create(
        offering=offering_world["offering"],
        student=offering_world["student"],
        actor=offering_world["admin"],
    )
    assert enrollment.pk is not None
    assert enrollment.eligible_for_outcomes is True

    # Duplicate rejected
    with pytest.raises(ValidationError):
        svc.create(
            offering=offering_world["offering"],
            student=offering_world["student"],
            actor=offering_world["admin"],
        )

    # Status update
    updated = svc.update_status(
        enrollment=enrollment,
        status=Enrollment.Status.WITHDRAWN,
        reason="Medical leave",
        actor=offering_world["admin"],
    )
    assert updated.status == Enrollment.Status.WITHDRAWN
    assert updated.eligible_for_outcomes is False
    assert updated.status_events.count() == 2


def test_controllers_constructor_injection():
    off_ctrl = CourseOfferingController()
    assert isinstance(off_ctrl.service, CourseOfferingService)
    assert isinstance(off_ctrl.enrollment_service, EnrollmentService)

    ia_ctrl = InstructorAssignmentController()
    assert isinstance(ia_ctrl.service, InstructorAssignmentService)

    enr_ctrl = EnrollmentController()
    assert isinstance(enr_ctrl.service, EnrollmentService)
