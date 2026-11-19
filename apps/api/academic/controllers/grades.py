from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..decorators import controller, get, patch, post, require_permission, validate_payload
from ..serializers import (
    GradeBatchSerializer,
    GradeHistorySerializer,
    GradeSerializer,
    GradeUpdateSerializer,
    GradeWriteSerializer,
)
from ..services import academic_service_provider
from ..services.grades import (
    GradeBatchService,
    GradeService,
    GradeVersionConflict,
)
from .base import AcademicPagination


@controller("grades", basename="grade")
class GradeController(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for grades with constructor injection and guard protection."""

    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def __init__(self, service: GradeService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(GradeService)

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post()
    @require_permission("grades.edit", scope_field="enrollment.offering")
    @validate_payload(GradeWriteSerializer)
    def create(self, request, *args, payload=None, **kwargs):
        grade = self.service.create(actor=request.user, **payload)
        return Response(GradeSerializer(grade).data, status=status.HTTP_201_CREATED)

    @patch("{id}")
    @require_permission("grades.edit", scope_field="offering")
    @validate_payload(GradeUpdateSerializer)
    def partial_update(self, request, *args, payload=None, **kwargs):
        grade = self.get_object()
        try:
            updated = self.service.correct(grade=grade, actor=request.user, **payload)
        except GradeVersionConflict as exc:
            return Response(
                {
                    "code": "version_conflict",
                    "detail": "The grade was changed by someone else.",
                    "current_version": exc.current_version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(GradeSerializer(updated).data)

    @get("{id}/history")
    @require_permission("grades.edit", scope_field="offering")
    def history(self, request, *args, **kwargs):
        grade = self.get_object()
        rows = self.service.history(grade=grade)
        return Response(GradeHistorySerializer(rows, many=True).data)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


@controller("grade-batches", basename="grade-batch")
class GradeBatchController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for grade batches with constructor injection and guard protection."""

    serializer_class = GradeBatchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination
    http_method_names = ["get", "post", "head", "options"]

    def __init__(self, service: GradeBatchService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(GradeBatchService)

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post()
    @require_permission("grades.edit", scope_field="offering")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @post("{id}/release")
    @require_permission("grades.edit", scope_field="offering")
    def release(self, request, *args, **kwargs):
        batch = self.get_object()
        released = self.service.release(batch=batch, actor=request.user)
        return Response(self.get_serializer(released).data)

    def perform_create(self, serializer):
        serializer.instance = self.service.create(**serializer.validated_data)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
