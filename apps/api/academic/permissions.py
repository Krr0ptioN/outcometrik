from rest_framework.permissions import SAFE_METHODS, BasePermission


class CanManageAcademicStructure(BasePermission):
    """PLACEHOLDER: any signed-in user may read (scoped); only staff may write.

    Replace with AUTH-01 coordinator/admin role checks.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(user.is_staff or user.is_superuser)
