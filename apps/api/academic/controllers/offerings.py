from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..decorators import controller, validate_payload
from ..serializers import CourseOfferingSerializer, EnrollmentSerializer
from ..services import CourseOfferingService, EnrollmentService
from .base import AcademicController


@controller("offerings", basename="offering")
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
    @validate_payload(
        EnrollmentSerializer,
        merge_data=lambda self, request, pk=None: {"offering": str(self.get_object().pk)},
    )
    def create_enrollment(self, request, pk=None, payload=None):
        """Add roster row for this offering."""
        service = self.get_service(EnrollmentService)
        enrollment = service.create(**payload)
        serializer = EnrollmentSerializer(enrollment, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)
