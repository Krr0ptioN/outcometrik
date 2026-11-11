from access.models import RoleAssignment
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .. import policy, scoping
from ..access_control import require
from ..models import (
    Enrollment,
    EnrollmentStatusEvent,
)
from .base import AcademicService
from .offerings import bump_revisions


class EnrollmentService(AcademicService):
    model = Enrollment
    immutable_fields = ("offering", "student")

    def visible_queryset(self, queryset):
        return scoping.scope_enrollments(self.actor, queryset)

    def create_access(self, data):
        return "offering.manage", data["offering"].pk

    def update_access(self, instance):
        return "grades.edit", instance.offering_id

    @transaction.atomic
    def create(self, *, offering, student, status=Enrollment.Status.ENROLLED, attempt_number=1):
        require(self.actor, "offering.manage", offering.pk)
        if not RoleAssignment.objects.filter(
            user=student, scope_id=offering.pk, role_id="student", revoked_at__isnull=True
        ).exists():
            raise ValidationError("The student must have an active student role in this offering.")
        if not student.is_active:
            raise ValidationError("The student account must be active before enrollment.")
        enrollment = Enrollment(
            offering=offering,
            student=student,
            status=status,
            attempt_number=attempt_number,
        )
        try:
            enrollment.save()
        except IntegrityError as exc:
            raise ValidationError("This student is already enrolled in this offering.") from exc
        EnrollmentStatusEvent.objects.create(
            enrollment=enrollment,
            from_status="",
            to_status=enrollment.status,
            eligible=enrollment.eligible_for_outcomes,
            policy_version=enrollment.eligibility_policy_version,
            reason="created",
            changed_by=self.actor,
        )
        if enrollment.eligible_for_outcomes:
            bump_revisions(program_id=offering.program_id, offering_id=offering.pk)
        return enrollment

    @transaction.atomic
    def update_status(self, *, enrollment, status, reason=""):
        require(self.actor, "grades.edit", enrollment.offering_id)
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
            changed_by=self.actor,
        )
        if was_eligible != enrollment.eligible_for_outcomes:
            bump_revisions(
                program_id=enrollment.offering.program_id,
                offering_id=enrollment.offering_id,
            )
        return enrollment
