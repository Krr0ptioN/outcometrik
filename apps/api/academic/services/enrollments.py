from typing import Any

from access.models import RoleAssignment
from access.policy import AuthorizationService
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from wireup import injectable

from .. import policy, scoping
from ..models import (
    Enrollment,
    EnrollmentStatusEvent,
)
from .revisions import RevisionTracker


@injectable
class EnrollmentService:
    """Manages student course enrollments with explicit dependency injection and actor scoping."""

    model = Enrollment
    immutable_fields = ("offering", "student")

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Enrollment.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Enrollment.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_enrollments(effective_actor, queryset)

    @transaction.atomic
    def create(
        self,
        *,
        offering,
        student,
        status=Enrollment.Status.ENROLLED,
        attempt_number=1,
        **extra,
    ) -> Enrollment:
        effective_actor = extra.get("actor", self.actor)
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
            changed_by=effective_actor,
        )
        if enrollment.eligible_for_outcomes:
            RevisionTracker.bump(program_id=offering.program_id, offering_id=offering.pk)
        return enrollment

    @transaction.atomic
    def update_status(self, *, enrollment, status, reason="", actor=None) -> Enrollment:
        effective_actor = actor or self.actor
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
            changed_by=effective_actor,
        )
        if was_eligible != enrollment.eligible_for_outcomes:
            RevisionTracker.bump(
                program_id=enrollment.offering.program_id,
                offering_id=enrollment.offering_id,
            )
        return enrollment

    @transaction.atomic
    def update(self, *, instance: Enrollment, **data) -> Enrollment:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        if "status" in data:
            return self.update_status(
                enrollment=instance,
                status=data["status"],
                reason=data.get("reason", ""),
            )
        for field, value in data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
