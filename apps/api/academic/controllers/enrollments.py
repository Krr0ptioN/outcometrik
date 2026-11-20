from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..decorators import controller, get, patch, post, scoped_permission, validate_payload
from ..serializers import EnrollmentSerializer, EnrollmentStatusUpdateSerializer
from ..services import EnrollmentService, academic_service_provider
from .base import AcademicPagination


@controller("enrollments", basename="enrollment")
class EnrollmentController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for enrollments with constructor injection and guard protection."""

    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(self, service: EnrollmentService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(EnrollmentService)

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
            scoped_permission("offering.manage", scope_field="offering"),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @patch(
        "{id}",
        permission_classes=[
            IsAuthenticated,
            scoped_permission("grades.edit", scope_field="offering"),
        ],
    )
    @validate_payload(EnrollmentStatusUpdateSerializer)
    def partial_update(self, request, *args, payload=None, **kwargs):
        enrollment = self.get_object()
        updated = self.service.update_status(
            enrollment=enrollment,
            status=payload["status"],
            reason=payload.get("reason", ""),
            actor=request.user,
        )
        return Response(self.get_serializer(updated).data)

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
