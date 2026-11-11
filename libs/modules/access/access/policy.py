"""One policy shared by HTTP adapters, selectors and domain services."""

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import DirectCapabilityGrant, RoleAssignment, Scope

CAPABILITIES = (
    "access.manage",
    "accounts.create",
    "program.manage",
    "offering.manage",
    "grades.view",
    "grades.edit",
    "grades.release",
    "outcomes.view",
    "evidence.view",
    "faculty.preview",
    "grades.export",
)


@dataclass(frozen=True)
class ResourceContext:
    # Domain code supplies these facts from stored records, never request payloads.
    owner_id: int | None = None
    released: bool = False
    published: bool = False


class AuthorizationService:
    def scope_ids(self, principal, capability):
        if (
            capability not in CAPABILITIES
            or not principal
            or not principal.is_authenticated
            or not principal.is_active
        ):
            return set(), set()
        roles = RoleAssignment.objects.filter(
            user=principal,
            revoked_at__isnull=True,
            role__capabilities__code=capability,
        ).exclude(role_id="student")
        # Only roles inherit to descendants. Direct grants apply to exactly one scope.
        inherited = set(roles.values_list("scope_id", flat=True))
        exact = set(
            DirectCapabilityGrant.objects.filter(
                user=principal,
                revoked_at__isnull=True,
                capability_id=capability,
            ).values_list("scope_id", flat=True)
        )
        return inherited, exact

    def scope_filter(self, principal, capability, prefix="scope"):
        inherited, exact = self.scope_ids(principal, capability)
        root = f"{prefix}_id" if prefix else "pk"
        parent = f"{prefix}__" if prefix else ""
        return (
            Q(**{f"{root}__in": inherited | exact})
            | Q(**{f"{parent}parent_id__in": inherited})
            | Q(**{f"{parent}parent__parent_id__in": inherited})
        )

    def student_filter(self, principal, capability, prefix="scope"):
        ids = RoleAssignment.objects.filter(
            user=principal,
            role_id="student",
            revoked_at__isnull=True,
            role__capabilities__code=capability,
        ).values_list("scope_id", flat=True)
        return Q(**{f"{prefix}_id__in": ids})

    def allows(self, *, principal, capability, scope, resource=None):
        if capability not in CAPABILITIES:
            return False
        if not principal or not principal.is_authenticated or not principal.is_active:
            return False
        if (
            Scope.objects.filter(pk=scope.pk)
            .filter(self.scope_filter(principal, capability, prefix=""))
            .exists()
        ):
            return True
        if resource is None or resource.owner_id != principal.pk:
            return False
        if capability not in {"grades.view", "outcomes.view", "evidence.view"}:
            return False
        if capability in {"grades.view", "evidence.view"} and not resource.released:
            return False
        if capability == "outcomes.view" and not resource.published:
            return False
        return RoleAssignment.objects.filter(
            user=principal,
            scope_id=scope.pk,
            role_id="student",
            revoked_at__isnull=True,
        ).exists()

    def require(self, **kwargs):
        if not self.allows(**kwargs):
            raise PermissionDenied("This action is not permitted in this scope.")


authorization = AuthorizationService()
