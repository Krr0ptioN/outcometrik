from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, DirectCapabilityGrant, InstitutionMembership, RoleAssignment
from .policy import authorization


@transaction.atomic
def assign(*, actor, user, scope, role=None, capability=None):
    authorization.require(principal=actor, capability="access.manage", scope=scope)
    if (role is None) == (capability is None):
        raise ValidationError("Supply exactly one role or capability.")
    if not user.is_active:
        raise ValidationError("The recipient must be active.")
    if role is not None and role.scope_kind != scope.kind:
        raise ValidationError("Role is invalid for this scope kind.")
    # Serialize grants/revocations in this scope to make idempotency race-safe.
    type(scope).objects.select_for_update().get(pk=scope.pk)
    institution = scope
    while institution.parent_id:
        institution = institution.parent
    InstitutionMembership.objects.get_or_create(user=user, institution=institution)
    model = RoleAssignment if role is not None else DirectCapabilityGrant
    field = {"role": role} if role is not None else {"capability": capability}
    assignment, created = model.objects.get_or_create(
        user=user,
        scope=scope,
        revoked_at__isnull=True,
        defaults={},
        **field,
    )
    if created:
        AuditEvent.objects.create(
            actor=actor,
            subject=user,
            scope=scope,
            action="role.assigned" if role else "capability.granted",
            metadata={
                "assignment_id": str(assignment.pk),
                "role": role.pk if role else None,
                "capability": capability.pk if capability else None,
            },
        )
    return assignment


@transaction.atomic
def revoke(*, actor, assignment):
    authorization.require(principal=actor, capability="access.manage", scope=assignment.scope)
    type(assignment.scope).objects.select_for_update().get(pk=assignment.scope_id)
    assignment = type(assignment).objects.select_for_update().get(pk=assignment.pk)
    if assignment.revoked_at is None:
        if (
            isinstance(assignment, RoleAssignment)
            and assignment.role_id == "administrator"
            and not RoleAssignment.objects.filter(
                scope_id=assignment.scope_id,
                role_id="administrator",
                revoked_at__isnull=True,
                user__is_active=True,
            )
            .exclude(pk=assignment.pk)
            .exists()
        ):
            raise ValidationError(
                "Assign another active administrator before revoking the last one."
            )
        assignment.revoked_at = timezone.now()
        assignment.save(update_fields=["revoked_at"])
        AuditEvent.objects.create(
            actor=actor,
            subject=assignment.user,
            scope=assignment.scope,
            action="role.revoked"
            if isinstance(assignment, RoleAssignment)
            else "capability.revoked",
            metadata={"assignment_id": str(assignment.pk)},
        )
    return assignment


@transaction.atomic
def sensitive_export(*, actor, scope, queryset, serialize):
    """Serialize a scope-bound, visibility-filtered export and audit before returning it."""
    from .selectors import visible_resources

    authorization.require(principal=actor, capability="grades.export", scope=scope)
    rows = visible_resources(
        queryset.filter(scope_id=scope.pk), principal=actor, capability="grades.view"
    )
    payload = serialize(rows)
    AuditEvent.objects.create(
        actor=actor, scope=scope, action="grades.exported", metadata={"count": rows.count()}
    )
    return payload
