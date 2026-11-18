from rest_framework.routers import Route, SimpleRouter


class AcademicRouter(SimpleRouter):
    """Router that merges discrete `@action` methods sharing the same URL path.

    In standard DRF SimpleRouter, registering multiple `@action` methods with the same
    `url_path` produces duplicate URL patterns where the first pattern shadows subsequent
    verbs (returning 405 Method Not Allowed).

    AcademicRouter combines actions targeting the same `(url, detail)` into a single Route
    mapping (`{'get': 'list_...', 'post': 'create_...'}`), enabling discrete,
    single-responsibility methods akin to NestJS (`@Get()`, `@Post()`) and Spring Boot
    (`@GetMapping`, `@PostMapping`).
    """

    def get_routes(self, viewset):
        routes = super().get_routes(viewset)
        merged_routes = []
        routes_by_key = {}

        for route in routes:
            if not isinstance(route, Route):
                merged_routes.append(route)
                continue

            key = (route.url, route.detail)
            if key not in routes_by_key:
                routes_by_key[key] = route
                merged_routes.append(route)
            else:
                existing_route = routes_by_key[key]
                combined_mapping = dict(existing_route.mapping)
                combined_mapping.update(route.mapping)
                combined_initkwargs = dict(existing_route.initkwargs)
                combined_initkwargs.update(route.initkwargs)

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
