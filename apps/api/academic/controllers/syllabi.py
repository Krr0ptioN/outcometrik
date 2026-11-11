from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..serializers import (
    AssessmentSerializer,
    LearningOutcomeSerializer,
    SyllabusCreateSerializer,
    SyllabusSerializer,
)
from ..services import SyllabusService
from .base import AcademicController


class SyllabusController(AcademicController):
    """HTTP surface for versioned syllabi. Lifecycle rules live in the service."""

    serializer_class = SyllabusSerializer
    service_class = SyllabusService
    filter_fields = ("offering", "status")
    ordering = ("offering", "version")

    def create(self, request, *args, **kwargs):
        serializer = SyllabusCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            syllabus = self.get_service().create(**serializer.validated_data)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(
            self.get_serializer(syllabus).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        syllabus = self.get_object()
        try:
            approved = self.get_service().approve(syllabus=syllabus)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(self.get_serializer(approved).data)

    @action(detail=True, methods=["post"])
    def revise(self, request, pk=None):
        syllabus = self.get_object()
        try:
            revision = self.get_service().revise(syllabus=syllabus)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(self.get_serializer(revision).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="retire")
    def retire(self, request, pk=None):
        syllabus = self.get_object()
        try:
            retired = self.get_service().remove_unused_draft(syllabus=syllabus)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(self.get_serializer(retired).data)

    @action(detail=True, methods=["get", "post"], url_path="learning-outcomes")
    def learning_outcomes(self, request, pk=None):
        """Return or add draft LO rows for this syllabus version."""
        syllabus = self.get_object()
        service = self.get_service()
        if request.method == "POST":
            serializer = LearningOutcomeSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                outcome = service.add_learning_outcome(
                    syllabus=syllabus, **serializer.validated_data
                )
            except DjangoValidationError as exc:
                self.raise_validation_error(exc)
            return Response(
                LearningOutcomeSerializer(outcome).data, status=status.HTTP_201_CREATED
            )
        queryset = syllabus.learning_outcomes.order_by("order", "created_at")
        return Response(LearningOutcomeSerializer(queryset, many=True).data)

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"learning-outcomes/(?P<child_pk>[^/.]+)",
    )
    def learning_outcome_detail(self, request, pk=None, child_pk=None):
        """Edit one draft LO. Resolving via the syllabus prevents cross-references."""
        syllabus = self.get_object()
        outcome = syllabus.learning_outcomes.filter(pk=child_pk).first()
        if outcome is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = LearningOutcomeSerializer(outcome, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            updated = self.get_service().update_learning_outcome(
                instance=outcome, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(LearningOutcomeSerializer(updated).data)

    @action(detail=True, methods=["get", "post"], url_path="assessments")
    def assessments(self, request, pk=None):
        """Return or add draft assessment rows for this syllabus version."""
        syllabus = self.get_object()
        service = self.get_service()
        if request.method == "POST":
            serializer = AssessmentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                assessment = service.add_assessment(syllabus=syllabus, **serializer.validated_data)
            except DjangoValidationError as exc:
                self.raise_validation_error(exc)
            return Response(
                AssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED
            )
        queryset = syllabus.assessments.order_by("order", "created_at")
        return Response(AssessmentSerializer(queryset, many=True).data)

    @action(detail=True, methods=["patch"], url_path=r"assessments/(?P<child_pk>[^/.]+)")
    def assessment_detail(self, request, pk=None, child_pk=None):
        """Edit one draft assessment, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        assessment = syllabus.assessments.filter(pk=child_pk).first()
        if assessment is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentSerializer(assessment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            updated = self.get_service().update_assessment(
                instance=assessment, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)
        return Response(AssessmentSerializer(updated).data)
