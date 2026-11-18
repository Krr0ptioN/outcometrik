from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..serializers import CourseOfferingSerializer, EnrollmentSerializer
from ..services import CourseOfferingService, EnrollmentService
from .base import AcademicController


class CourseOfferingController(AcademicController):
    serializer_class = CourseOfferingSerializer
    service_class = CourseOfferingService
    filter_fields = ("program", "course", "term", "section", "status")

    @action(detail=True, methods=["get"], url_path="enrollments", url_name="enrollments")
    def list_enrollments(self, request, pk=None):
        """Return roster rows for this offering."""
        offering = self.get_object()
        service = self.get_service(EnrollmentService)
        queryset = service.get_queryset().filter(offering=offering).order_by("created_at", "id")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(
            EnrollmentSerializer(page, many=True, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], url_path="enrollments", url_name="enrollments")
    def create_enrollment(self, request, pk=None):
        """Add roster row for this offering."""
        offering = self.get_object()
        service = self.get_service(EnrollmentService)
        serializer = EnrollmentSerializer(
            data={**request.data, "offering": str(offering.pk)},
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        try:
            enrollment = service.create(**serializer.validated_data)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        serializer.instance = enrollment
        return Response(serializer.data, status=status.HTTP_201_CREATED)
