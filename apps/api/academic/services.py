from access.models import Role, RoleAssignment, Scope
from access.services import assign
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F

from . import policy
from .models import CourseOffering, Enrollment, EnrollmentStatusEvent, Program


def _bump_revisions(*, program_id, offering_id=None) -> None:
    Program.objects.filter(pk=program_id).update(input_revision=F("input_revision") + 1)
    if offering_id is not None:
        CourseOffering.objects.filter(pk=offering_id).update(input_revision=F("input_revision") + 1)


def _save_unique(instance, message: str) -> None:
    try:
        with transaction.atomic():
            instance.save()
    except IntegrityError as exc:  # concurrent duplicate that passed the pre-check
        raise ValidationError(message) from exc


@transaction.atomic
def create_offering(*, actor, program, course, term, section, status=CourseOffering.Status.ACTIVE):
    from .access_control import require

    require(actor, "offering.manage", program.pk)
    offering = CourseOffering(
        program=program, course=course, term=term, section=section, status=status
    )
    _save_unique(offering, "This offering already exists.")
    if offering.status == CourseOffering.Status.ACTIVE:
        _bump_revisions(program_id=program.pk)
    return offering


@transaction.atomic
def create_enrollment(
    *, actor, offering, student, status=Enrollment.Status.ENROLLED, attempt_number=1
):
    from .access_control import require

    require(actor, "offering.manage", offering.pk)
    if not RoleAssignment.objects.filter(
        user=student, scope_id=offering.pk, role_id="student", revoked_at__isnull=True
    ).exists():
        raise ValidationError("The student must have an active student role in this offering.")
    if not student.is_active:
        raise ValidationError("The student account must be active before enrollment.")
    enrollment = Enrollment(
        offering=offering, student=student, status=status, attempt_number=attempt_number
    )
    _save_unique(enrollment, "This student is already enrolled in this offering.")
    EnrollmentStatusEvent.objects.create(
        enrollment=enrollment,
        from_status="",
        to_status=enrollment.status,
        eligible=enrollment.eligible_for_outcomes,
        policy_version=enrollment.eligibility_policy_version,
        reason="created",
        changed_by=actor,
    )
    if enrollment.eligible_for_outcomes:
        _bump_revisions(program_id=offering.program_id, offering_id=offering.pk)
    return enrollment


@transaction.atomic
def update_enrollment_status(*, actor, enrollment, status, reason=""):
    from .access_control import require

    require(actor, "grades.edit", enrollment.offering_id)
    enrollment = (
        Enrollment.objects.select_for_update().select_related("offering").get(pk=enrollment.pk)
    )
    if status == enrollment.status:
        return enrollment
    was_eligible = enrollment.eligible_for_outcomes
    old_status = enrollment.status
    enrollment.status = status
    enrollment.apply_policy()
    enrollment.save()
    EnrollmentStatusEvent.objects.create(
        enrollment=enrollment,
        from_status=old_status,
        to_status=status,
        eligible=enrollment.eligible_for_outcomes,
        policy_version=policy.POLICY_VERSION,
        reason=reason,
        changed_by=actor,
    )
    if was_eligible != enrollment.eligible_for_outcomes:
        _bump_revisions(
            program_id=enrollment.offering.program_id, offering_id=enrollment.offering_id
        )
    return enrollment


@transaction.atomic
def create_instructor_assignment(*, actor, offering, user, assignment_role):
    from .access_control import require

    require(actor, "access.manage", offering.pk)
    if not user.is_active:
        raise ValidationError("The instructor account must be active.")
    from .models import InstructorAssignment

    assignment, _ = InstructorAssignment.objects.get_or_create(
        offering=offering, user=user, defaults={"assignment_role": assignment_role}
    )
    if assignment_role == InstructorAssignment.Role.INSTRUCTOR:
        assign(
            actor=actor,
            user=user,
            scope=Scope.objects.get(pk=offering.pk),
            role=Role.objects.get(pk="instructor"),
        )
    return assignment
