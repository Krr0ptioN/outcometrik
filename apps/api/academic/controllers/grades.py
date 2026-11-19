from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..serializers import (
    GradeBatchSerializer,
    GradeHistorySerializer,
    GradeSerializer,
    GradeUpdateSerializer,
    GradeWriteSerializer,
)
from ..services.grades import (
    GradeBatchService,
    GradeService,
    GradeVersionConflict,
)
from .base import AcademicController, validate_payload


class GradeController(AcademicController):
    serializer_class = GradeSerializer
    service_class = GradeService
    filter_fields = ("offering", "enrollment", "assessment", "batch", "state")
    http_method_names = ["get", "post", "patch", "head", "options"]

    @validate_payload(GradeWriteSerializer)
    def create(self, request, *args, payload=None, **kwargs):
        grade = self.get_service().create(**payload)
        return Response(GradeSerializer(grade).data, status=status.HTTP_201_CREATED)

    @validate_payload(GradeUpdateSerializer)
    def partial_update(self, request, *args, payload=None, **kwargs):
        grade = self.get_object()
        try:
            updated = self.get_service().correct(grade=grade, **payload)
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

    @action(detail=True, methods=["get"])
    def history(self, request, *args, **kwargs):
        grade = self.get_object()
        rows = self.get_service().history(grade=grade)
        return Response(GradeHistorySerializer(rows, many=True).data)


class GradeBatchController(AcademicController):
    serializer_class = GradeBatchSerializer
    service_class = GradeBatchService
    filter_fields = ("offering",)
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=True, methods=["post"])
    def release(self, request, *args, **kwargs):
        batch = self.get_object()
        released = self.get_service().release(batch=batch)
        return Response(self.get_serializer(released).data)
