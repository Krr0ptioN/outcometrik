from django.core.exceptions import ValidationError as DjangoValidationError
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
from .base import AcademicController


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
    def activate(self, request, pk=None):
        instance = self.get_object()
        payload = ProgramOutcomeSetActivateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            instance = self.get_service().activate(instance=instance, **payload.validated_data)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["get", "post"])
    def outcomes(self, request, pk=None):
        po_set = self.get_object()
        if request.method == "GET":
            return Response(
                ProgramOutcomeSerializer(po_set.outcomes.order_by("ordering"), many=True).data
            )
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        data["outcome_set"] = str(po_set.pk)
        serializer = ProgramOutcomeSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            outcome = ProgramOutcomeService(actor=request.user).create(**serializer.validated_data)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(ProgramOutcomeSerializer(outcome).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"outcomes/(?P<child_pk>[^/.]+)")
    def outcome_detail(self, request, pk=None, child_pk=None):
        po_set = self.get_object()
        outcome = po_set.outcomes.filter(pk=child_pk).first()
        if outcome is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ProgramOutcomeSerializer(outcome, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            outcome = ProgramOutcomeService(actor=request.user).update(
                instance=outcome, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(ProgramOutcomeSerializer(outcome).data)


class ProgramOutcomeController(AcademicController):
    serializer_class = ProgramOutcomeSerializer
    service_class = ProgramOutcomeService
    filter_fields = ("outcome_set", "code")
