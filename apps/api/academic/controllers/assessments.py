from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from ..decorators import controller, get
from ..serializers import AssessmentSerializer
from ..services import AssessmentService, academic_service_provider
from .base import AcademicPagination


@controller("assessments", basename="assessment")
class AssessmentController(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for assessments with constructor injection and read-only access."""

    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination
    http_method_names = ["get", "head", "options"]

    def __init__(self, service: AssessmentService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(AssessmentService)

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
