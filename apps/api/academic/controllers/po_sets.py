from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..serializers import ProgramOutcomeSerializer, ProgramOutcomeSetSerializer
from ..services.po_sets import ProgramOutcomeSetService
from .base import AcademicController


class ProgramOutcomeSetController(AcademicController):
    serializer_class = ProgramOutcomeSetSerializer
    service_class = ProgramOutcomeSetService
    filter_fields = ("program", "active")

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        try:
            instance = self.get_service().activate(instance=self.get_object())
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["get", "post"])
    def outcomes(self, request, pk=None):
        po_set = self.get_object()
        if request.method == "GET":
            return Response(
                ProgramOutcomeSerializer(po_set.outcomes.order_by("order"), many=True).data
            )
        serializer = ProgramOutcomeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            outcome = self.get_service().save_outcome(po_set=po_set, **serializer.validated_data)
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
            outcome = self.get_service().save_outcome(
                po_set=po_set, outcome=outcome, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(ProgramOutcomeSerializer(outcome).data)
