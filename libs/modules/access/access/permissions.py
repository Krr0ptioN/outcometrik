"""DRF adapter. Views must filter list/detail querysets with access.selectors."""

from rest_framework.permissions import BasePermission

from .policy import authorization


class HasCapability(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active)

    def has_object_permission(self, request, view, obj):
        return authorization.allows(
            principal=request.user,
            capability=view.required_capability,
            scope=obj.scope,
            resource=view.resource_context(obj),
        )
