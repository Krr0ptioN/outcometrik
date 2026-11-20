from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..decorators import controller, get, post, scoped_permission, validate_payload
from ..serializers import (
    OutcomeScoreSerializer,
    PublicationCreateSerializer,
    PublicationSerializer,
)
from ..services import PublicationConflict, PublicationService, academic_service_provider
from .base import AcademicPagination


@controller("publications", basename="publication")
class PublicationController(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """HTTP surface for immutable outcome publications, stale detection, and scoped score reads."""

    serializer_class = PublicationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination
    http_method_names = ["get", "post", "head", "options"]

    def __init__(self, service: PublicationService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(PublicationService)

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["publication_service"] = self.service
        return context

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post(
        permission_classes=[
            IsAuthenticated,
            scoped_permission("outcomes.publish", scope_field="run.program"),
        ]
    )
    @validate_payload(PublicationCreateSerializer)
    def create(self, request, *args, payload=None, **kwargs):
        try:
            publication, replayed = self.service.publish(actor=request.user, **payload)
        except PublicationConflict as exc:
            return Response(
                {"code": exc.code, "detail": exc.detail},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = PublicationSerializer(publication, context=self.get_serializer_context())
        return Response(
            serializer.data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
        )

    @get("{id}/scores", url_name="scores")
    def scores(self, request, *args, **kwargs):
        publication = self.get_object()
        filters = dict(request.query_params.items())
        rows = self.service.list_scores(publication=publication, actor=request.user, **filters)
        return Response(OutcomeScoreSerializer(rows, many=True).data)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
