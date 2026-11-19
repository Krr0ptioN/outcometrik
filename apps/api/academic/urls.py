import academic.controllers  # noqa: F401 - ensure controllers are imported and registered via @controller

from .router import academic_router

urlpatterns = academic_router.urls
