from django.core.exceptions import ValidationError as DjangoValidationError
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
from ..services.grades import GradeBatchService, GradeService, GradeVersionConflict
from .base import AcademicController


class GradeController(AcademicController):
    serializer_class = GradeSerializer
    service_class = GradeService
    filter_fields = ("offering", "enrollment", "assessment", "batch", "state")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def create(self, request, *args, **kwargs):
        serializer = GradeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            grade = self.get_service().create(**serializer.validated_data)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(GradeSerializer(grade).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        grade = self.get_object()
        serializer = GradeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = self.get_service().correct(grade=grade, **serializer.validated_data)
        except GradeVersionConflict as exc:
            return Response(
                {
                    "code": "version_conflict",
                    "detail": str(exc),
                    "current_version": exc.current_version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
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
        try:
            released = self.get_service().release(batch=batch)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(self.get_serializer(released).data)
