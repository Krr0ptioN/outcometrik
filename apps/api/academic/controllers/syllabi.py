from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..serializers import (
    LearningOutcomeSerializer,
    SyllabusAssessmentSerializer,
    SyllabusCreateSerializer,
    SyllabusSerializer,
)
from ..services import SyllabusService
from .base import AcademicController, validate_payload


class SyllabusController(AcademicController):
    """HTTP surface for versioned syllabi. Lifecycle rules live in the service."""

    serializer_class = SyllabusSerializer
    service_class = SyllabusService
    filter_fields = ("offering", "status")
    ordering = ("offering", "version")

    @validate_payload(SyllabusCreateSerializer)
    def create(self, request, *args, payload=None, **kwargs):
        syllabus = self.get_service().create(**payload)
        return Response(self.get_serializer(syllabus).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        syllabus = self.get_object()
        approved = self.get_service().approve(syllabus=syllabus)
        return Response(self.get_serializer(approved).data)

    @action(detail=True, methods=["post"])
    def revise(self, request, pk=None):
        syllabus = self.get_object()
        revision = self.get_service().revise(syllabus=syllabus)
        return Response(self.get_serializer(revision).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="bind-active-po-set")
    def bind_active_po_set(self, request, pk=None):
        syllabus = self.get_service().bind_active_po_set(syllabus=self.get_object())
        return Response(self.get_serializer(syllabus).data)

    @action(detail=True, methods=["post"], url_path="retire")
    def retire(self, request, pk=None):
        syllabus = self.get_object()
        retired = self.get_service().remove_unused_draft(syllabus=syllabus)
        return Response(self.get_serializer(retired).data)

    @action(
        detail=True,
        methods=["get"],
        url_path="learning-outcomes",
        url_name="learning-outcomes",
    )
    def list_learning_outcomes(self, request, pk=None):
        """Return draft LO rows for this syllabus version."""
        syllabus = self.get_object()
        queryset = syllabus.learning_outcomes.order_by("order", "created_at")
        return Response(LearningOutcomeSerializer(queryset, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="learning-outcomes",
        url_name="learning-outcomes",
    )
    @validate_payload(LearningOutcomeSerializer)
    def create_learning_outcome(self, request, pk=None, payload=None):
        """Add draft LO row for this syllabus version."""
        syllabus = self.get_object()
        outcome = self.get_service().add_learning_outcome(syllabus=syllabus, **payload)
        return Response(LearningOutcomeSerializer(outcome).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"learning-outcomes/(?P<child_pk>[^/.]+)",
        url_name="learning-outcome-detail",
    )
    @validate_payload(LearningOutcomeSerializer, partial=True)
    def update_learning_outcome(self, request, pk=None, child_pk=None, payload=None):
        """Edit one draft LO, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        outcome = syllabus.learning_outcomes.filter(pk=child_pk).first()
        if outcome is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        updated = self.get_service().update_learning_outcome(instance=outcome, **payload)
        return Response(LearningOutcomeSerializer(updated).data)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"learning-outcomes/(?P<child_pk>[^/.]+)",
        url_name="learning-outcome-detail",
    )
    def delete_learning_outcome(self, request, pk=None, child_pk=None):
        """Remove one draft LO, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        outcome = syllabus.learning_outcomes.filter(pk=child_pk).first()
        if outcome is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        self.get_service().delete_learning_outcome(instance=outcome)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="assessments", url_name="assessments")
    def list_assessments(self, request, pk=None):
        """Return draft assessment rows for this syllabus version."""
        syllabus = self.get_object()
        queryset = syllabus.assessments.order_by("order", "created_at")
        return Response(SyllabusAssessmentSerializer(queryset, many=True).data)

    @action(detail=True, methods=["post"], url_path="assessments", url_name="assessments")
    @validate_payload(SyllabusAssessmentSerializer)
    def create_assessment(self, request, pk=None, payload=None):
        """Add draft assessment row for this syllabus version."""
        syllabus = self.get_object()
        assessment = self.get_service().add_assessment(syllabus=syllabus, **payload)
        return Response(
            SyllabusAssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"assessments/(?P<child_pk>[^/.]+)",
        url_name="assessment-detail",
    )
    @validate_payload(SyllabusAssessmentSerializer, partial=True)
    def update_assessment(self, request, pk=None, child_pk=None, payload=None):
        """Edit one draft assessment, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        assessment = syllabus.assessments.filter(pk=child_pk).first()
        if assessment is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        updated = self.get_service().update_assessment(instance=assessment, **payload)
        return Response(SyllabusAssessmentSerializer(updated).data)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"assessments/(?P<child_pk>[^/.]+)",
        url_name="assessment-detail",
    )
    def delete_assessment(self, request, pk=None, child_pk=None):
        """Remove one draft assessment, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        assessment = syllabus.assessments.filter(pk=child_pk).first()
        if assessment is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        self.get_service().delete_assessment(instance=assessment)
        return Response(status=status.HTTP_204_NO_CONTENT)
