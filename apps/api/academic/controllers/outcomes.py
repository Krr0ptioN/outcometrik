from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import ProgramOutcomeSet
from ..serializers import (
    ProgramOutcomeSerializer,
    ProgramOutcomeSetActivateSerializer,
    ProgramOutcomeSetSerializer,
)
from ..services import ProgramOutcomeService, ProgramOutcomeSetService
from .base import AcademicController, validate_payload


class ProgramOutcomeSetController(AcademicController):
    serializer_class = ProgramOutcomeSetSerializer
    service_class = ProgramOutcomeSetService
    filter_fields = ("program", "status", "version")

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list" and "active" in self.request.query_params:
            val = self.request.query_params["active"].lower() in ("true", "1")
            if val:
                queryset = queryset.filter(status=ProgramOutcomeSet.Status.ACTIVE)
            else:
                queryset = queryset.filter(status=ProgramOutcomeSet.Status.DRAFT)
        return queryset

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=["post"])
    @validate_payload(ProgramOutcomeSetActivateSerializer)
    def activate(self, request, pk=None, payload=None):
        instance = self.get_service().activate(instance=self.get_object(), **payload)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["get"], url_path="outcomes", url_name="outcomes")
    def list_outcomes(self, request, pk=None):
        po_set = self.get_object()
        return Response(
            ProgramOutcomeSerializer(po_set.outcomes.order_by("ordering"), many=True).data
        )

    @action(detail=True, methods=["post"], url_path="outcomes", url_name="outcomes")
    @validate_payload(
        ProgramOutcomeSerializer,
        merge_data=lambda self, request, pk=None: {"outcome_set": str(self.get_object().pk)},
    )
    def create_outcome(self, request, pk=None, payload=None):
        outcome = ProgramOutcomeService(actor=request.user).create(**payload)
        return Response(ProgramOutcomeSerializer(outcome).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"outcomes/(?P<child_pk>[^/.]+)",
        url_name="outcome-detail",
    )
    @validate_payload(ProgramOutcomeSerializer, partial=True)
    def update_outcome(self, request, pk=None, child_pk=None, payload=None):
        po_set = self.get_object()
        outcome = po_set.outcomes.filter(pk=child_pk).first()
        if outcome is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        outcome = ProgramOutcomeService(actor=request.user).update(instance=outcome, **payload)
        return Response(ProgramOutcomeSerializer(outcome).data)


class ProgramOutcomeController(AcademicController):
    serializer_class = ProgramOutcomeSerializer
    service_class = ProgramOutcomeService
    filter_fields = ("outcome_set", "code")
