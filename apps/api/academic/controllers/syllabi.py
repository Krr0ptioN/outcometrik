from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..decorators import (
    controller,
    delete,
    get,
    patch,
    post,
    require_permission,
    validate_payload,
)
from ..serializers import (
    AssessmentLOMappingSerializer,
    AssessmentLOMatrixReplaceSerializer,
    LearningOutcomeSerializer,
    LOPOMappingSerializer,
    LOPOMatrixReplaceSerializer,
    SyllabusAssessmentSerializer,
    SyllabusCreateSerializer,
    SyllabusSerializer,
)
from ..services import (
    SyllabusMappingVersionConflict,
    SyllabusService,
    academic_service_provider,
)
from .base import AcademicPagination


@controller("syllabi", basename="syllabus")
class SyllabusController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """HTTP surface for versioned syllabi with constructor injection and guard protection."""

    serializer_class = SyllabusSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(self, service: SyllabusService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(SyllabusService)

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post()
    @require_permission("syllabus.draft", scope_field="offering")
    @validate_payload(SyllabusCreateSerializer)
    def create(self, request, *args, payload=None, **kwargs):
        syllabus = self.service.create(**payload)
        return Response(self.get_serializer(syllabus).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @post("{id}/approve")
    @require_permission("syllabus.approve", scope_field="offering.program")
    def approve(self, request, pk=None):
        syllabus = self.get_object()
        approved = self.service.approve(syllabus=syllabus, actor=request.user)
        return Response(self.get_serializer(approved).data)

    @post("{id}/revise")
    @require_permission("syllabus.draft", scope_field="offering")
    def revise(self, request, pk=None):
        syllabus = self.get_object()
        revision = self.service.revise(syllabus=syllabus)
        return Response(self.get_serializer(revision).data, status=status.HTTP_201_CREATED)

    @post("{id}/bind-active-po-set")
    @require_permission("syllabus.draft", scope_field="offering")
    def bind_active_po_set(self, request, pk=None):
        syllabus = self.service.bind_active_po_set(syllabus=self.get_object())
        return Response(self.get_serializer(syllabus).data)

    @post("{id}/retire")
    @require_permission("syllabus.draft", scope_field="offering")
    def retire(self, request, pk=None):
        syllabus = self.get_object()
        retired = self.service.remove_unused_draft(syllabus=syllabus)
        return Response(self.get_serializer(retired).data)

    @get("{id}/learning-outcomes", url_name="learning-outcomes")
    def list_learning_outcomes(self, request, pk=None):
        """Return draft LO rows for this syllabus version."""
        syllabus = self.get_object()
        queryset = syllabus.learning_outcomes.order_by("order", "created_at")
        return Response(LearningOutcomeSerializer(queryset, many=True).data)

    @post("{id}/learning-outcomes", url_name="learning-outcomes")
    @require_permission("syllabus.draft", scope_field="offering")
    @validate_payload(LearningOutcomeSerializer)
    def create_learning_outcome(self, request, pk=None, payload=None):
        """Add draft LO row for this syllabus version."""
        syllabus = self.get_object()
        outcome = self.service.add_learning_outcome(syllabus=syllabus, **payload)
        return Response(LearningOutcomeSerializer(outcome).data, status=status.HTTP_201_CREATED)

    @patch(r"{id}/learning-outcomes/(?P<child_pk>[^/.]+)", url_name="learning-outcome-detail")
    @require_permission("syllabus.draft", scope_field="offering")
    @validate_payload(LearningOutcomeSerializer, partial=True)
    def update_learning_outcome(self, request, pk=None, child_pk=None, payload=None):
        """Edit one draft LO, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        outcome = syllabus.learning_outcomes.filter(pk=child_pk).first()
        if outcome is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        updated = self.service.update_learning_outcome(instance=outcome, **payload)
        return Response(LearningOutcomeSerializer(updated).data)

    @delete(r"{id}/learning-outcomes/(?P<child_pk>[^/.]+)", url_name="learning-outcome-detail")
    @require_permission("syllabus.draft", scope_field="offering")
    def delete_learning_outcome(self, request, pk=None, child_pk=None):
        """Remove one draft LO, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        outcome = syllabus.learning_outcomes.filter(pk=child_pk).first()
        if outcome is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        self.service.delete_learning_outcome(instance=outcome)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @get("{id}/assessments", url_name="assessments")
    def list_assessments(self, request, pk=None):
        """Return draft assessment rows for this syllabus version."""
        syllabus = self.get_object()
        queryset = syllabus.assessments.order_by("order", "created_at")
        return Response(SyllabusAssessmentSerializer(queryset, many=True).data)

    @post("{id}/assessments", url_name="assessments")
    @require_permission("syllabus.draft", scope_field="offering")
    @validate_payload(SyllabusAssessmentSerializer)
    def create_assessment(self, request, pk=None, payload=None):
        """Add draft assessment row for this syllabus version."""
        syllabus = self.get_object()
        assessment = self.service.add_assessment(syllabus=syllabus, **payload)
        return Response(
            SyllabusAssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED
        )

    @patch(r"{id}/assessments/(?P<child_pk>[^/.]+)", url_name="assessment-detail")
    @require_permission("syllabus.draft", scope_field="offering")
    @validate_payload(SyllabusAssessmentSerializer, partial=True)
    def update_assessment(self, request, pk=None, child_pk=None, payload=None):
        """Edit one draft assessment, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        assessment = syllabus.assessments.filter(pk=child_pk).first()
        if assessment is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        updated = self.service.update_assessment(instance=assessment, **payload)
        return Response(SyllabusAssessmentSerializer(updated).data)

    @delete(r"{id}/assessments/(?P<child_pk>[^/.]+)", url_name="assessment-detail")
    @require_permission("syllabus.draft", scope_field="offering")
    def delete_assessment(self, request, pk=None, child_pk=None):
        """Remove one draft assessment, scoped through its owning syllabus version."""
        syllabus = self.get_object()
        assessment = syllabus.assessments.filter(pk=child_pk).first()
        if assessment is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        self.service.delete_assessment(instance=assessment)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @get("{id}/assessment-lo-mappings", url_name="assessment-lo-mappings")
    def list_assessment_lo_mappings(self, request, pk=None):
        """Return A->LO mapping rows for this syllabus version."""
        syllabus = self.get_object()
        queryset = syllabus.assessment_lo_mappings.order_by(
            "assessment__order", "learning_outcome__order", "created_at"
        )
        return Response(AssessmentLOMappingSerializer(queryset, many=True).data)

    @post("{id}/assessment-lo-mappings", url_name="assessment-lo-mappings")
    @require_permission("syllabus.draft", scope_field="offering")
    @validate_payload(AssessmentLOMatrixReplaceSerializer)
    def replace_assessment_lo_mappings(self, request, pk=None, payload=None):
        """Atomically replace the A->LO mapping matrix with optimistic locking."""
        syllabus = self.get_object()
        try:
            updated = self.service.replace_assessment_lo_matrix(
                syllabus=syllabus,
                expected_revision=payload["expected_revision"],
                mappings=payload["mappings"],
            )
        except SyllabusMappingVersionConflict as exc:
            return Response(
                {
                    "code": "version_conflict",
                    "detail": "The syllabus mapping matrix was modified by another user.",
                    "current_revision": exc.current_revision,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self.get_serializer(updated).data)

    @get("{id}/lo-po-mappings", url_name="lo-po-mappings")
    def list_lo_po_mappings(self, request, pk=None):
        """Return LO->PO mapping rows for this syllabus version."""
        syllabus = self.get_object()
        queryset = syllabus.lo_po_mappings.order_by(
            "learning_outcome__order", "program_outcome__ordering", "created_at"
        )
        return Response(LOPOMappingSerializer(queryset, many=True).data)

    @post("{id}/lo-po-mappings", url_name="lo-po-mappings")
    @require_permission("syllabus.draft", scope_field="offering")
    @validate_payload(LOPOMatrixReplaceSerializer)
    def replace_lo_po_mappings(self, request, pk=None, payload=None):
        """Atomically replace the LO->PO mapping matrix with optimistic locking."""
        syllabus = self.get_object()
        try:
            updated = self.service.replace_lo_po_matrix(
                syllabus=syllabus,
                expected_revision=payload["expected_revision"],
                mappings=payload["mappings"],
            )
        except SyllabusMappingVersionConflict as exc:
            return Response(
                {
                    "code": "version_conflict",
                    "detail": "The syllabus mapping matrix was modified by another user.",
                    "current_revision": exc.current_revision,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self.get_serializer(updated).data)

    @get("{id}/mapping-validation", url_name="mapping-validation")
    def get_mapping_validation(self, request, pk=None):
        """Return diagnostic report of MAPPED/UNMAPPED LOs, ASSESSED/NOT_ASSESSED POs, and approval readiness."""
        syllabus = self.get_object()
        report = self.service.validate_mappings(syllabus=syllabus)
        return Response(report)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
