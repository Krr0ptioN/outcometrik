class AcademicServiceProvider:
    """Composition root that injects the request actor into a service instance."""

    def provide(self, service_class, *, actor):
        return service_class(actor=actor)


academic_service_provider = AcademicServiceProvider()
