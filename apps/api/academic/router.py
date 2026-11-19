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
        merged_routes = []
        routes_by_key = {}

        for route_item in routes:
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


def controller(
    prefix: str,
    *,
    basename: str | None = None,
    router: AcademicRouter | None = None,
) -> Callable[[type], type]:
    """Class decorator that registers a controller with the routing system.

    Analogous to NestJS `@Controller('path')`.
    Registers DRF ViewSets with the router, or APIViews as standalone endpoints.
    """

    def decorator(cls: type) -> type:
        target_router = router or academic_router
        target_router.register_controller(prefix, cls, basename=basename)
        cls._controller_prefix = prefix
        return cls

    return decorator


def route(
    method: str,
    path_suffix: str = "",
    *,
    detail: bool = False,
    **action_kwargs: Any,
) -> Callable:
    """Action route decorator analogous to NestJS `@Get()`, `@Post()`, etc.

    Wraps DRF `@action` with clean HTTP verb semantics.
    """
    from rest_framework.decorators import action

    url_path = path_suffix.strip("/") if path_suffix else None

    def decorator(func: Callable) -> Callable:
        return action(
            detail=detail,
            methods=[method.lower()],
            url_path=url_path,
            **action_kwargs,
        )(func)

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
