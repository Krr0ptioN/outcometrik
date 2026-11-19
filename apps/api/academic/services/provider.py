from access.policy import AuthorizationService


class AcademicServiceProvider:
    """Composition root that resolves services through Wireup container or direct instantiation."""

    def provide(self, service_class, *, actor=None):
        try:
            from wireup.integration.django import get_app_container
            from wireup.ioc.container.async_container import async_container_force_sync_scope

            container = get_app_container()
            with async_container_force_sync_scope(container) as scoped:
                instance = scoped.get(service_class)
                if actor is not None and hasattr(instance, "actor"):
                    instance.actor = actor
                return instance
        except Exception:  # noqa: BLE001 - wireup container resolution fallback
            try:
                return service_class(actor=actor)
            except TypeError:
                return service_class(AuthorizationService(), actor=actor)


academic_service_provider = AcademicServiceProvider()
