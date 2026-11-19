from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..decorators import controller, get, post, require_permission, validate_payload
from ..serializers import (
    CalculationRunSerializer,
    OfferingCalculationRunCreateSerializer,
    OutcomeScoreSerializer,
    ProgramCalculationRunCreateSerializer,
)
from ..services import CalculationService, academic_service_provider
from .base import AcademicPagination


@controller("calculation-runs", basename="calculation-run")
class CalculationRunController(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """HTTP surface for offering and cumulative program outcome calculation runs."""

    serializer_class = CalculationRunSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination
    http_method_names = ["get", "post", "head", "options"]

    def __init__(self, service: CalculationService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(CalculationService)

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post("offering", url_name="run-offering")
    @require_permission("grades.view", scope_field="offering")
    @validate_payload(OfferingCalculationRunCreateSerializer)
    def run_offering(self, request, *args, payload=None, **kwargs):
        run, created = self.service.run_offering(offering=payload["offering"], actor=request.user)
        return Response(
            CalculationRunSerializer(run).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @post("program", url_name="run-program")
    @require_permission("outcomes.view", scope_field="program")
    @validate_payload(ProgramCalculationRunCreateSerializer)
    def run_program(self, request, *args, payload=None, **kwargs):
        run, created = self.service.run_program(program=payload["program"], actor=request.user)
        return Response(
            CalculationRunSerializer(run).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @get("{id}/scores", url_name="scores")
    def scores(self, request, *args, **kwargs):
        run = self.get_object()
        filters = dict(request.query_params.items())
        rows = self.service.list_scores(run=run, **filters)
        return Response(OutcomeScoreSerializer(rows, many=True).data)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
