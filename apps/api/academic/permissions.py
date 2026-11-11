from rest_framework.permissions import BasePermission


class CanManageAcademicStructure(BasePermission):
    """Authenticated reads are filtered by selectors; writes need a scoped capability."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        capability, scope_id = view.object_write_scope(obj)
        from .access_control import require

        require(request.user, capability, scope_id)
        return True
