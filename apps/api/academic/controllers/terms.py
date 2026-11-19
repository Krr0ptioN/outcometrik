from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from ..decorators import controller, require_permission
from ..serializers import AcademicTermSerializer
from ..services import AcademicTermService, academic_service_provider
from .base import AcademicPagination


@controller("terms", basename="term")
class AcademicTermController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for academic terms with explicit constructor injection and guard protection."""

    serializer_class = AcademicTermSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(self, service: AcademicTermService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(AcademicTermService)

    def get_queryset(self):
        return self.service.get_queryset(actor=self.request.user)

    @require_permission("access.manage", scope_field="institution")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @require_permission("access.manage", scope_field="institution")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @require_permission("access.manage", scope_field="institution")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.instance = self.service.create(**serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = self.service.update(
            instance=serializer.instance,
            **serializer.validated_data,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
