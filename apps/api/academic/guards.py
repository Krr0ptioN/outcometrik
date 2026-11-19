import functools
from collections.abc import Callable
from typing import Any

from django.core.exceptions import PermissionDenied


def require_permission(
    capability: str,
    *,
    scope_getter: Callable[..., Any] | None = None,
    scope_param: str | None = None,
) -> Callable:
    """Guard decorator that enforces RBAC/ABAC authorization before an action executes.

    Analogous to NestJS `@UseGuards(CapabilityGuard)`.
    Extracts the actor (`request.user`) and `scope_id`, then verifies capability.
    Raises `PermissionDenied` (DRF HTTP 403) if authorization fails or scope is missing.

    Arguments:
        capability: Code of the capability to check (e.g., 'grades.edit', 'program.manage').
        scope_getter: Optional callable `(self, request, *args, **kwargs)` returning the scope ID.
        scope_param: Optional parameter name to inspect in kwargs or request.data for scope ID.
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            actor = getattr(request, "user", None)
            scope_id = None

            if scope_getter is not None:
                scope_id = scope_getter(self, request, *args, **kwargs)
            elif scope_param is not None:
                if scope_param in kwargs:
                    scope_id = kwargs[scope_param]
                elif (
                    hasattr(request, "data")
                    and isinstance(request.data, dict)
                    and scope_param in request.data
                ):
                    scope_id = request.data[scope_param]
            elif "pk" in kwargs:
                scope_id = kwargs["pk"]

            if scope_id is None:
                raise PermissionDenied("This action is not permitted in this scope.")

            from .access_control import require

            require(actor, capability, scope_id)

            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator


guard = require_permission

__all__ = ["guard", "require_permission"]
