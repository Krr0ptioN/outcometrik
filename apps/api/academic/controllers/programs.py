from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from ..decorators import controller, get, patch, post, put, scoped_permission
from ..serializers import ProgramSerializer
from ..services import ProgramService, academic_service_provider
from .base import AcademicPagination


@controller("programs", basename="program")
class ProgramController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for programs with explicit constructor injection and guard protection."""

    serializer_class = ProgramSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(self, service: ProgramService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(ProgramService)

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post(
        permission_classes=[
            IsAuthenticated,
            scoped_permission("program.manage", scope_field="department.institution"),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @put("{id}", permission_classes=[IsAuthenticated, scoped_permission("program.manage")])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @patch("{id}", permission_classes=[IsAuthenticated, scoped_permission("program.manage")])
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
