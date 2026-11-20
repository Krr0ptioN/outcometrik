from collections.abc import Callable
from typing import Any

from django.urls import path
from rest_framework.routers import Route, SimpleRouter
from rest_framework.viewsets import ViewSetMixin


class AcademicRouter(SimpleRouter):
    """Router that merges discrete `@action` methods sharing the same URL path
    and auto-discovers controllers decorated with `@controller`.

    In standard DRF SimpleRouter, registering multiple `@action` methods with the same
    `url_path` produces duplicate URL patterns where the first pattern shadows subsequent
    verbs (returning 405 Method Not Allowed).

    AcademicRouter combines actions targeting the same `(url, detail)` into a single Route
    mapping (`{'get': 'list_...', 'post': 'create_...'}`), enabling discrete,
    single-responsibility methods akin to NestJS (`@Get()`, `@Post()`) and Spring Boot
    (`@GetMapping`, `@PostMapping`).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._extra_urlpatterns: list[Any] = []
        self._registered_prefixes: set[str] = set()

    def register_controller(
        self,
        prefix: str,
        viewset_or_view: type,
        basename: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Registers a controller class with the router.

        If the controller is a DRF ViewSet, registers with `self.register(...)`.
        If it is an APIView (or regular View), registers as a direct URL pattern.
        """
        clean_prefix = prefix.strip("/")
        base = basename or clean_prefix.replace("/", "-")

        if issubclass(viewset_or_view, ViewSetMixin):
            # Avoid duplicate registrations
            if not any(r[0] == clean_prefix for r in self.registry):
                self.register(clean_prefix, viewset_or_view, basename=base, **kwargs)
                self._registered_prefixes.add(clean_prefix)
        else:
            route_pattern = path(f"{clean_prefix}/", viewset_or_view.as_view(), name=base)
            if not any(
                str(p.pattern) == str(route_pattern.pattern) for p in self._extra_urlpatterns
            ):
                self._extra_urlpatterns.append(route_pattern)
                self._registered_prefixes.add(clean_prefix)

    @property
    def urls(self):
        return super().urls + self._extra_urlpatterns

    def get_routes(self, viewset):
        routes = super().get_routes(viewset)

        # Inspect viewset methods for explicit route decorators targeting root or detail
        root_overrides: dict[str, str] = {}
        detail_overrides: dict[str, str] = {}
        for attr_name in dir(viewset):
            attr = getattr(viewset, attr_name, None)
            if hasattr(attr, "_http_route"):
                meta = attr._http_route
                if not meta["path"]:
                    if meta["detail"]:
                        detail_overrides[meta["method"]] = attr_name
                    else:
                        root_overrides[meta["method"]] = attr_name

        updated_routes = []
        for r in routes:
            if not isinstance(r, Route):
                updated_routes.append(r)
                continue
            if r.url == "^{prefix}{trailing_slash}$" and not r.detail and root_overrides:
                mapping = dict(r.mapping)
                mapping.update(root_overrides)
                r = Route(
                    url=r.url,
                    mapping=mapping,
                    name=r.name,
                    detail=r.detail,
                    initkwargs=r.initkwargs,
                )
            elif r.url == "^{prefix}/{lookup}{trailing_slash}$" and r.detail and detail_overrides:
                mapping = dict(r.mapping)
                mapping.update(detail_overrides)
                r = Route(
                    url=r.url,
                    mapping=mapping,
                    name=r.name,
                    detail=r.detail,
                    initkwargs=r.initkwargs,
                )
            updated_routes.append(r)

        merged_routes = []
        routes_by_key = {}

        for route_item in updated_routes:
            if not isinstance(route_item, Route):
                merged_routes.append(route_item)
                continue

            key = (route_item.url, route_item.detail)
            if key not in routes_by_key:
                routes_by_key[key] = route_item
                merged_routes.append(route_item)
            else:
                existing_route = routes_by_key[key]
                combined_mapping = dict(existing_route.mapping)
                combined_mapping.update(route_item.mapping)
                combined_initkwargs = dict(existing_route.initkwargs)
                combined_initkwargs.update(route_item.initkwargs)

                merged_route = Route(
                    url=existing_route.url,
                    mapping=combined_mapping,
                    name=existing_route.name,
                    detail=existing_route.detail,
                    initkwargs=combined_initkwargs,
                )
                routes_by_key[key] = merged_route
                idx = merged_routes.index(existing_route)
                merged_routes[idx] = merged_route

        return merged_routes


# Default global router instance for academic domain controllers
academic_router = AcademicRouter()


def _install_action_permissions(cls: type) -> None:
    """Wire method-level `_drf_permission_classes` into DRF's native `get_permissions()`.

    Ensures DRF's standard `APIView.check_permissions()` and
    `GenericAPIView.check_object_permissions()` (inside `get_object()`) execute
    action-scoped `BasePermission` classes without custom method wrappers or
    duplicate object lookups.
    """
    if not hasattr(cls, "get_permissions") or getattr(cls, "_action_permissions_installed", False):
        return

    original_get_permissions = cls.get_permissions

    def get_permissions(self):
        perms = list(original_get_permissions(self))
        action_name = getattr(self, "action", None)
        if not action_name:
            req = getattr(self, "request", None)
            action_name = getattr(req, "method", "").lower() if req is not None else None
        handler = getattr(type(self), action_name, None) if action_name else None
        extra_classes = getattr(handler, "_drf_permission_classes", ()) if handler else ()
        if extra_classes:
            self._drf_action_permissions_enforced = True
            perms.extend(perm_cls() for perm_cls in extra_classes)
        return perms

    cls.get_permissions = get_permissions
    cls._action_permissions_installed = True


def controller(
    prefix: str,
    *,
    basename: str | None = None,
    router: AcademicRouter | None = None,
) -> Callable[[type], type]:
    """Class decorator that registers a controller with the routing system.

    Registers DRF ViewSets with the router, or APIViews as standalone endpoints,
    and wires any per-action DRF permission classes into `get_permissions()`.
    """

    def decorator(cls: type) -> type:
        _install_action_permissions(cls)
        target_router = router or academic_router
        target_router.register_controller(prefix, cls, basename=basename)
        cls._controller_prefix = prefix
        return cls

    return decorator


def _normalize_route(path_suffix: str = "", *, detail: bool = False) -> tuple[str, bool]:
    """Normalizes path declarations such as ':id', '{id}', '{pk}', or subpaths."""
    path = path_suffix.strip("/") if path_suffix else ""
    for token in (":id", "{id}", ":pk", "{pk}"):
        if path == token:
            return "", True
        if path.startswith(f"{token}/"):
            return path[len(token) + 1 :], True
    return path, detail


def route(
    method: str,
    path_suffix: str = "",
    *,
    detail: bool = False,
    **action_kwargs: Any,
) -> Callable:
    """Action route decorator analogous to NestJS `@Get()`, `@Post()`, etc.

    Supports:
    - Root collection: `@get()`, `@post()` (or `@get("")`, `@post("")`)
    - Detail instance: `@get("{id}")`, `@patch("{id}")`, `@get(detail=True)`
    - Sub-resources: `@get("stats")`, `@post("{id}/approve")`, `@post("approve", detail=True)`
    """
    from rest_framework.decorators import action

    clean_path, is_detail = _normalize_route(path_suffix, detail=detail)

    def decorator(func: Callable) -> Callable:
        func._http_route = {
            "method": method.lower(),
            "path": clean_path,
            "detail": is_detail,
        }
        if clean_path:
            return action(
                detail=is_detail,
                methods=[method.lower()],
                url_path=clean_path,
                **action_kwargs,
            )(func)
        return func

    return decorator


def get(path_suffix: str = "", *, detail: bool = False, **kwargs: Any) -> Callable:
    """Action route decorator for HTTP GET."""
    return route("get", path_suffix, detail=detail, **kwargs)


def post(path_suffix: str = "", *, detail: bool = False, **kwargs: Any) -> Callable:
    """Action route decorator for HTTP POST."""
    return route("post", path_suffix, detail=detail, **kwargs)


def put(path_suffix: str = "", *, detail: bool = False, **kwargs: Any) -> Callable:
    """Action route decorator for HTTP PUT."""
    return route("put", path_suffix, detail=detail, **kwargs)


def patch(path_suffix: str = "", *, detail: bool = False, **kwargs: Any) -> Callable:
    """Action route decorator for HTTP PATCH."""
    return route("patch", path_suffix, detail=detail, **kwargs)


def delete(path_suffix: str = "", *, detail: bool = False, **kwargs: Any) -> Callable:
    """Action route decorator for HTTP DELETE."""
    return route("delete", path_suffix, detail=detail, **kwargs)
