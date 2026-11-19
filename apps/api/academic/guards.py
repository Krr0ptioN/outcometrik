import functools
from collections.abc import Callable
from typing import Any

from django.core.exceptions import FieldDoesNotExist, PermissionDenied


def _extract_field_path(instance: Any, path: str) -> Any:
    parts = path.split(".")
    current = instance
    for i, part in enumerate(parts):
        if current is None:
            return None
        is_last = i == len(parts) - 1
        if is_last and hasattr(current, f"{part}_id"):
            current = getattr(current, f"{part}_id")
        elif hasattr(current, part):
            current = getattr(current, part)
        elif hasattr(current, f"{part}_id"):
            current = getattr(current, f"{part}_id")
        else:
            return None
    return getattr(current, "pk", current)


def _resolve_scope_from_data(view: Any, data: dict, scope_field: str) -> Any:
    if scope_field == "name":
        from access.models import Scope

        name = data.get("name")
        scope = (
            Scope.objects.filter(kind=Scope.Kind.INSTITUTION, label=name).first() if name else None
        )
        return scope.pk if scope else None

    parts = scope_field.split(".")
    first_field = parts[0]
    val = data.get(first_field)
    if val is None:
        return None
    if len(parts) == 1:
        return getattr(val, "pk", val)

    svc = getattr(view, "service", None)
    model_cls = getattr(svc, "model", None)
    if model_cls is None and hasattr(view, "get_queryset"):
        try:
            model_cls = view.get_queryset().model
        except (AttributeError, TypeError):
            model_cls = None

    if model_cls is not None and hasattr(model_cls, "_meta"):
        try:
            rel_field = model_cls._meta.get_field(first_field)
            rel_model = rel_field.remote_field.model
            target = rel_model.objects.filter(pk=getattr(val, "pk", val)).first()
            if target is not None:
                return _extract_field_path(target, ".".join(parts[1:]))
        except (AttributeError, FieldDoesNotExist):
            return getattr(val, "pk", val)

    return getattr(val, "pk", val)


def require_permission(
    capability: str,
    *,
    scope_field: str | None = None,
    scope_param: str | None = None,
    scope_getter: Callable[..., Any] | None = None,
) -> Callable:
    """Guard decorator that enforces RBAC/ABAC authorization before an action executes.

    Analogous to NestJS `@UseGuards(CapabilityGuard)`.
    Extracts the actor (`request.user`) and `scope_id`, then verifies capability.
    Raises `PermissionDenied` (DRF HTTP 403) if authorization fails or scope is missing.

    Arguments:
        capability: Code of the capability to check (e.g., 'grades.edit', 'access.manage').
        scope_field: Declarative path to scope on model/payload (e.g., 'institution', 'home_department.institution', 'name').
        scope_param: Optional parameter name to inspect in kwargs or request.data for scope ID.
        scope_getter: Optional custom callable `(self, request, *args, **kwargs)` returning the scope ID.
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
                else:
                    payload = getattr(request, "data", getattr(request, "POST", {}))
                    if isinstance(payload, dict) and scope_param in payload:
                        scope_id = payload[scope_param]
            elif scope_field is not None:
                if "pk" in kwargs:
                    instance = None
                    model_cls = getattr(getattr(self, "service", None), "model", None)
                    if model_cls is not None:
                        instance = model_cls.objects.filter(pk=kwargs["pk"]).first()
                    if instance is None and hasattr(self, "get_object"):
                        instance = self.get_object()
                    scope_id = _extract_field_path(instance, scope_field)
                else:
                    payload = getattr(request, "data", getattr(request, "POST", {}))
                    if isinstance(payload, dict):
                        scope_id = _resolve_scope_from_data(self, payload, scope_field)
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
