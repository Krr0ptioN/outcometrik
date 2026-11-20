from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from ..decorators import controller, get, patch, post, scoped_permission
from ..serializers import InstructorAssignmentSerializer
from ..services import InstructorAssignmentService, academic_service_provider
from .base import AcademicPagination


@controller("instructor-assignments", basename="instructor-assignment")
class InstructorAssignmentController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for instructor assignments with constructor injection and guard protection."""

    serializer_class = InstructorAssignmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(self, service: InstructorAssignmentService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(InstructorAssignmentService)

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
            scoped_permission("access.manage", scope_field="offering"),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @patch(
        "{id}",
        permission_classes=[
            IsAuthenticated,
            scoped_permission("access.manage", scope_field="offering"),
        ],
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.instance = self.service.create(
            actor=self.request.user,
            **serializer.validated_data,
        )

    def perform_update(self, serializer):
        serializer.instance = self.service.update(
            instance=serializer.instance,
            **serializer.validated_data,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
