from typing import TypeVar

from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

T = TypeVar("T")


class WireupServiceProvider:
    """Resolves registered @injectable services from Wireup's Django application container."""

    def provide(self, service_class: type[T]) -> T:
        container = get_app_container()
        with async_container_force_sync_scope(container) as scoped:
            return scoped.get(service_class)


academic_service_provider = WireupServiceProvider()
