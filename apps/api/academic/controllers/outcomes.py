from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..decorators import (
    controller,
    get,
    patch,
    post,
    scoped_permission,
    validate_payload,
)
from ..models import ProgramOutcomeSet
from ..serializers import (
    ProgramOutcomeSerializer,
    ProgramOutcomeSetActivateSerializer,
    ProgramOutcomeSetSerializer,
)
from ..services import (
    ProgramOutcomeService,
    ProgramOutcomeSetService,
    academic_service_provider,
)
from .base import AcademicPagination


@controller("po-sets", basename="po-set")
@controller("program-outcome-sets", basename="program-outcome-set")
class ProgramOutcomeSetController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for program outcome sets with constructor injection and guard protection."""

    serializer_class = ProgramOutcomeSetSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(
        self,
        service: ProgramOutcomeSetService | None = None,
        outcome_service: ProgramOutcomeService | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(ProgramOutcomeSetService)
        self.outcome_service = outcome_service or academic_service_provider.provide(
            ProgramOutcomeService
        )

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        if "active" in self.request.query_params:
            val = self.request.query_params["active"].lower() in ("true", "1")
            filters["status"] = (
                ProgramOutcomeSet.Status.ACTIVE if val else ProgramOutcomeSet.Status.DRAFT
            )
            filters.pop("active", None)
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post(
        permission_classes=[
            IsAuthenticated,
            scoped_permission("program.manage", scope_field="program"),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @post(
        "{id}/activate",
        permission_classes=[
            IsAuthenticated,
            scoped_permission("program.manage", scope_field="program"),
        ],
    )
    @validate_payload(ProgramOutcomeSetActivateSerializer)
    def activate(self, request, pk=None, payload=None):
        instance = self.service.activate(
            instance=self.get_object(),
            actor=request.user,
            **payload,
        )
        return Response(self.get_serializer(instance).data)

    @get("{id}/outcomes")
    def list_outcomes(self, request, pk=None):
        po_set = self.get_object()
        return Response(
            ProgramOutcomeSerializer(po_set.outcomes.order_by("ordering"), many=True).data
        )

    @post(
        "{id}/outcomes",
        permission_classes=[
            IsAuthenticated,
            scoped_permission("program.manage", scope_field="program"),
        ],
    )
    @validate_payload(
        ProgramOutcomeSerializer,
        merge_data=lambda self, request, pk=None: {"outcome_set": str(self.get_object().pk)},
    )
    def create_outcome(self, request, pk=None, payload=None):
        outcome = self.outcome_service.create(**payload)
        return Response(ProgramOutcomeSerializer(outcome).data, status=status.HTTP_201_CREATED)

    @patch(
        r"{id}/outcomes/(?P<child_pk>[^/.]+)",
        permission_classes=[
            IsAuthenticated,
            scoped_permission("program.manage", scope_field="program"),
        ],
    )
    @validate_payload(ProgramOutcomeSerializer, partial=True)
    def update_outcome(self, request, pk=None, child_pk=None, payload=None):
        po_set = self.get_object()
        outcome = po_set.outcomes.filter(pk=child_pk).first()
        if outcome is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        outcome = self.outcome_service.update(instance=outcome, **payload)
        return Response(ProgramOutcomeSerializer(outcome).data)

    def perform_create(self, serializer):
        serializer.instance = self.service.create(**serializer.validated_data)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


@controller("program-outcomes", basename="program-outcome")
class ProgramOutcomeController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for individual program outcomes with constructor injection and guard protection."""

    serializer_class = ProgramOutcomeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(self, service: ProgramOutcomeService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(ProgramOutcomeService)

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post(
        permission_classes=[
            IsAuthenticated,
            scoped_permission("program.manage", scope_field="outcome_set.program"),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @patch(
        "{id}",
        permission_classes=[
            IsAuthenticated,
            scoped_permission("program.manage", scope_field="outcome_set.program"),
        ],
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.instance = self.service.create(**serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = self.service.update(
            instance=serializer.instance,
            **serializer.validated_data,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
