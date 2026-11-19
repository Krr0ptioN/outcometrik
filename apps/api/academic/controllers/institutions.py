from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from ..guards import require_permission
from ..serializers import InstitutionSerializer
from ..services import InstitutionService, academic_service_provider
from .base import AcademicPagination


class InstitutionController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for institutions with explicit constructor injection and guard protection."""

    serializer_class = InstitutionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(self, service: InstitutionService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(InstitutionService)

    def get_queryset(self):
        return self.service.get_queryset(actor=self.request.user)

    @require_permission("access.manage", scope_field="name")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @require_permission("access.manage")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @require_permission("access.manage")
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
