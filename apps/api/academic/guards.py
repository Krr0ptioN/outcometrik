"""DRF-native scoped RBAC/ABAC permission classes and action permission helpers.

Integrates `access.policy.authorization` directly into Django REST Framework's
`BasePermission` lifecycle (`has_permission` / `has_object_permission` /
`get_permissions`) so:
- Collection/action checks run inside DRF's `initial()` via `check_permissions()`.
- Detail/instance checks run automatically inside `self.get_object()` via
  `check_object_permissions()` (preserving 404 on scoped-out objects with a single DB query).
- Permission classes compose natively with DRF `&`, `|`, `~` operators and standard
  `IsAuthenticated`.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from rest_framework.permissions import BasePermission


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


def _resolve_scope_from_data(view: Any, data: Any, scope_field: str) -> Any:
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


def _is_allowed(actor: Any, capability: str, scope_id: Any) -> bool:
    if scope_id is None:
        return False
    from .access_control import require

    try:
        require(actor, capability, scope_id)
    except PermissionDenied:
        return False
    return True


def _resolve_request_scope(
    view: Any,
    request: Any,
    *,
    scope_field: str | None = None,
    scope_param: str | None = None,
    scope_getter: Callable[..., Any] | None = None,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
) -> Any:
    kw = kwargs if kwargs is not None else getattr(view, "kwargs", {}) or {}
    if scope_getter is not None:
        return scope_getter(view, request, *args, **kw)
    if scope_param is not None:
        if scope_param in kw:
            return kw[scope_param]
        payload = getattr(request, "data", getattr(request, "POST", {}))
        if hasattr(payload, "get") and scope_param in payload:
            return payload.get(scope_param)
        query_params = getattr(request, "query_params", getattr(request, "GET", {}))
        if hasattr(query_params, "get") and scope_param in query_params:
            return query_params.get(scope_param)
        return None
    if scope_field is not None:
        payload = getattr(request, "data", getattr(request, "POST", {}))
        if hasattr(payload, "get"):
            scope_id = _resolve_scope_from_data(view, payload, scope_field)
            if scope_id is not None:
                return scope_id
        query_params = getattr(request, "query_params", getattr(request, "GET", {}))
        if hasattr(query_params, "get"):
            return _resolve_scope_from_data(view, query_params, scope_field)
    return None


class HasScopedCapability(BasePermission):
    """DRF `BasePermission` enforcing scoped RBAC/ABAC capabilities.

    Subclass or instantiate via `scoped_permission(...)` to attach directly to
    DRF's `permission_classes`, `get_permissions()`, or `@action(permission_classes=...)`.
    """

    message = "This action is not permitted in this scope."
    capability: str = ""
    scope_field: str | None = None
    scope_param: str | None = None
    scope_getter: Callable[..., Any] | None = None

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False

        view_kwargs = getattr(view, "kwargs", {}) or {}
        if self.scope_getter is None and self.scope_param is None and "pk" in view_kwargs:
            # Detail routes defer to `has_object_permission` inside `self.get_object()`
            # so scoped-out records still return 404 before 403 and only query once.
            if hasattr(view, "get_object"):
                return True
            return _is_allowed(user, self.capability, view_kwargs["pk"])

        scope_id = _resolve_request_scope(
            view,
            request,
            scope_field=self.scope_field,
            scope_param=self.scope_param,
            scope_getter=self.scope_getter,
        )
        return _is_allowed(user, self.capability, scope_id)

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if self.scope_getter is not None or self.scope_param is not None:
            # Already checked at view level in `has_permission`.
            return True
        scope_id = (
            _extract_field_path(obj, self.scope_field)
            if self.scope_field
            else getattr(obj, "pk", None)
        )
        return _is_allowed(user, self.capability, scope_id)


def scoped_permission(
    capability: str,
    *,
    scope_field: str | None = None,
    scope_param: str | None = None,
    scope_getter: Callable[..., Any] | None = None,
) -> type[HasScopedCapability]:
    """Factory returning a DRF `BasePermission` class for a scoped capability.

    Because DRF expects classes in `permission_classes` (instantiating them in
    `get_permissions()`), this dynamically creates a `HasScopedCapability` subclass
    that works natively with `permission_classes`, `@action(permission_classes=...)`,
    and DRF's `&` / `|` / `~` permission composition operators.
    """
    safe_cap = capability.replace(".", "_").replace("-", "_")
    attrs: dict[str, Any] = {
        "capability": capability,
        "scope_field": scope_field,
        "scope_param": scope_param,
        "scope_getter": staticmethod(scope_getter) if scope_getter is not None else None,
    }
    return type(f"HasScopedCapability_{safe_cap}", (HasScopedCapability,), attrs)


def require_permission(
    capability: str,
    *,
    scope_field: str | None = None,
    scope_param: str | None = None,
    scope_getter: Callable[..., Any] | None = None,
) -> Callable:
    """Attach a DRF-native `HasScopedCapability` permission class to a controller action.

    When applied to a DRF ViewSet/APIView method registered with `@controller`,
    the permission class is attached as `_drf_permission_classes` so DRF's
    `get_permissions()` enforces it natively during `check_permissions()` and
    `check_object_permissions()` (inside `self.get_object()`), avoiding duplicate
    object lookups and bypassing nothing in DRF's permission pipeline.

    When a decorated method is called directly in isolation outside DRF's
    `dispatch()` lifecycle (e.g. plain Python unit tests), the wrapper evaluates
    the same `HasScopedCapability` instance and raises `PermissionDenied` on denial.
    """
    perm_cls = scoped_permission(
        capability,
        scope_field=scope_field,
        scope_param=scope_param,
        scope_getter=scope_getter,
    )

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Inside a DRF view that wired action permissions into `get_permissions()`,
            # DRF already ran `check_permissions()` in `initial()` and will run
            # `check_object_permissions()` inside `self.get_object()`.
            if getattr(self, "_drf_action_permissions_enforced", False):
                return view_func(self, request, *args, **kwargs)

            # Fallback for direct non-DRF unit test invocations of the method.
            perm = perm_cls()
            actor = getattr(request, "user", None)
            if scope_getter is None and scope_param is None and "pk" in kwargs:
                if hasattr(self, "get_object"):
                    instance = self.get_object()
                    allowed = perm.has_object_permission(request, self, instance)
                else:
                    allowed = _is_allowed(actor, capability, kwargs["pk"])
            else:
                scope_id = _resolve_request_scope(
                    self,
                    request,
                    scope_field=scope_field,
                    scope_param=scope_param,
                    scope_getter=scope_getter,
                    args=args,
                    kwargs=kwargs,
                )
                allowed = _is_allowed(actor, capability, scope_id)

            if not allowed:
                raise PermissionDenied(perm.message)

            return view_func(self, request, *args, **kwargs)

        existing = list(getattr(view_func, "_drf_permission_classes", ()))
        existing.append(perm_cls)
        wrapper._drf_permission_classes = tuple(existing)
        return wrapper

    return decorator


guard = require_permission

__all__ = ["HasScopedCapability", "guard", "require_permission", "scoped_permission"]
