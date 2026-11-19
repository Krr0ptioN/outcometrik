from rest_framework.response import Response

from ..decorators import controller, validate_payload
from ..serializers import EnrollmentSerializer, EnrollmentStatusUpdateSerializer
from ..services import EnrollmentService
from .base import AcademicController


@controller("enrollments", basename="enrollment")
class EnrollmentController(AcademicController):
    serializer_class = EnrollmentSerializer
    service_class = EnrollmentService
    filter_fields = ("offering", "student", "status", "eligible_for_outcomes")
    ordering = ("created_at", "id")

    @validate_payload(EnrollmentStatusUpdateSerializer)
    def partial_update(self, request, *args, payload=None, **kwargs):
        enrollment = self.get_object()
        updated = self.get_service().update_status(
            enrollment=enrollment,
            **payload,
        )
        return Response(self.get_serializer(updated).data)
