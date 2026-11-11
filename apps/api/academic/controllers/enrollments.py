from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.response import Response

from ..serializers import EnrollmentSerializer, EnrollmentStatusUpdateSerializer
from ..services import EnrollmentService
from .base import AcademicController


class EnrollmentController(AcademicController):
    serializer_class = EnrollmentSerializer
    service_class = EnrollmentService
    filter_fields = ("offering", "student", "status", "eligible_for_outcomes")
    ordering = ("created_at", "id")

    def perform_create(self, serializer):
        try:
            serializer.instance = self.get_service().create(**serializer.validated_data)
        except DjangoValidationError as exc:
            AcademicController.raise_validation_error(exc)

    def partial_update(self, request, *args, **kwargs):
        enrollment = self.get_object()
        serializer = EnrollmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = self.get_service().update_status(
                enrollment=enrollment,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            AcademicController.raise_validation_error(exc)
        return Response(self.get_serializer(updated).data)
