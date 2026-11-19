from typing import Any

from access.policy import AuthorizationService
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from wireup import injectable

from .. import scoping
from ..models import (
    AssessmentLOMapping,
    CourseOffering,
    CoursePOContribution,
    LearningOutcome,
    LOPOMapping,
    Program,
    ProgramOutcome,
    ProgramOutcomeSet,
    Syllabus,
    SyllabusAssessment,
)
from .revisions import RevisionTracker
from .syllabus_validation import SyllabusMappingVersionConflict, SyllabusValidator


@injectable
class SyllabusService:
    """Versioned syllabus lifecycle: draft, approve, revise, and mapping matrices.

    Draft configuration is editable; approval locks a version forever, and a
    revision clones the prior version into a new draft. Single-draft and
    single-official-version invariants are enforced with database constraints;
    authorization is delegated to controller-level guard policies ('syllabus.draft'
    at the offering scope, 'syllabus.approve' at the program scope).
    """

    model = Syllabus
    immutable_fields = ("offering", "version", "status")
    MANAGED_FIELDS = ("code", "description", "order")
    ASSESSMENT_FIELDS = ("code", "kind", "order", "is_required", "is_active", "max_points")

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Syllabus.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("offering", "version")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Syllabus.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_syllabi(effective_actor, queryset).prefetch_related(
            "learning_outcomes",
            "assessments",
            "po_contributions__program_outcome",
            "assessment_lo_mappings",
            "lo_po_mappings",
        )

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _lock_offering_row(offering_id):
        return CourseOffering.objects.select_for_update().get(pk=offering_id)

    @staticmethod
    def _editable(syllabus):
        return SyllabusValidator.validate_editable(syllabus)

    # -- lifecycle -------------------------------------------------------

    @transaction.atomic
    def create(self, *, offering, po_set_version=None, **extra) -> Syllabus:
        offering = self._lock_offering_row(offering.pk)
        active_set = (
            ProgramOutcomeSet.objects.filter(
                program_id=offering.program_id,
                status=ProgramOutcomeSet.Status.ACTIVE,
                effective_date__lte=timezone.localdate(),
            )
            .order_by("-effective_date")
            .first()
        )
        if po_set_version is None and active_set:
            po_set_version = active_set.version
        SyllabusValidator.validate_creation(offering)
        version = offering.syllabi.count() + 1
        syllabus = Syllabus(
            offering=offering,
            version=version,
            status=Syllabus.Status.DRAFT,
            po_set_version=po_set_version,
        )
        try:
            with transaction.atomic():
                syllabus.save()
        except IntegrityError as exc:
            raise ValidationError(
                "A conflicting syllabus version exists for this offering."
            ) from exc
        return syllabus

    @transaction.atomic
    def update(self, *, instance: Syllabus, **data) -> Syllabus:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            raise ValidationError(
                "A conflicting syllabus version exists for this offering."
            ) from exc
        return instance

    @transaction.atomic
    def approve(self, *, syllabus, actor: Any = None) -> Syllabus:
        effective_actor = actor or self.actor
        Program.objects.select_for_update().get(pk=syllabus.offering.program_id)
        # Lock every version row of this offering so no concurrent approve/create slips in.
        offering_versions = Syllabus.objects.select_for_update().filter(
            offering_id=syllabus.offering_id
        )
        syllabus = offering_versions.select_related("offering").get(pk=syllabus.pk)
        offering = syllabus.offering
        active_set = (
            ProgramOutcomeSet.objects.filter(
                program_id=offering.program_id,
                status=ProgramOutcomeSet.Status.ACTIVE,
                effective_date__lte=timezone.localdate(),
            )
            .order_by("-effective_date")
            .first()
        )
        SyllabusValidator.validate_approval(syllabus, active_set)
        # Supersede: a newer approved version retires the previously official one so
        # the single-official-version constraint holds across the whole history.
        offering_versions.exclude(pk=syllabus.pk).filter(status=Syllabus.Status.APPROVED).update(
            status=Syllabus.Status.RETIRED
        )
        syllabus.status = Syllabus.Status.APPROVED
        syllabus.approved_by = effective_actor
        syllabus.approved_at = timezone.now()
        try:
            with transaction.atomic():
                syllabus.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        except IntegrityError as exc:
            raise ValidationError(
                "Another syllabus version is already approved for this offering."
            ) from exc
        # Activating a syllabus changes calculation inputs; detect stale results.
        RevisionTracker.bump(program_id=offering.program_id, offering_id=offering.pk)
        return syllabus

    @transaction.atomic
    def revise(self, *, syllabus) -> Syllabus:
        syllabus = (
            Syllabus.objects.select_for_update().select_related("offering").get(pk=syllabus.pk)
        )
        offering = syllabus.offering
        SyllabusValidator.validate_revision(syllabus, offering)
        version = offering.syllabi.count() + 1

        active_set = (
            ProgramOutcomeSet.objects.filter(
                program_id=offering.program_id,
                status=ProgramOutcomeSet.Status.ACTIVE,
                effective_date__lte=timezone.localdate(),
            )
            .order_by("-effective_date")
            .first()
        )
        target_po_set_version = active_set.version if active_set else syllabus.po_set_version
        revision = Syllabus(
            offering=offering,
            version=version,
            status=Syllabus.Status.DRAFT,

            po_set_version=target_po_set_version,
        )
        try:
            with transaction.atomic():
                revision.save()
        except IntegrityError as exc:
            raise ValidationError("A conflicting draft revision already exists.") from exc

        lo_by_code: dict[str, LearningOutcome] = {}
        for lo in syllabus.learning_outcomes.all().order_by("order"):
            cloned_lo = LearningOutcome.objects.create(
                syllabus=revision, code=lo.code, description=lo.description, order=lo.order
            )
            lo_by_code[lo.code] = cloned_lo

        asmt_by_code: dict[str, SyllabusAssessment] = {}
        for a in syllabus.assessments.all().order_by("order"):
            cloned_asmt = SyllabusAssessment.objects.create(
                syllabus=revision,
                code=a.code,
                kind=a.kind,
                order=a.order,
                is_required=a.is_required,
                is_active=a.is_active,
                max_points=a.max_points,
            )
            asmt_by_code[a.code] = cloned_asmt

        for contrib in (
            syllabus.po_contributions.select_related("program_outcome")
            .all()
            .order_by("program_outcome__ordering")
        ):
            target_po = contrib.program_outcome
            if revision.po_set_version != syllabus.po_set_version and active_set is not None:
                target_po = ProgramOutcome.objects.filter(
                    outcome_set=active_set,
                    code=contrib.program_outcome.code,
                ).first()
            if target_po is not None:
                CoursePOContribution.objects.create(
                    syllabus=revision,
                    program_outcome=target_po,
                    weight=contrib.weight,
                )

        for m in syllabus.assessment_lo_mappings.select_related(
            "assessment", "learning_outcome"
        ).all():
            cloned_asmt = asmt_by_code.get(m.assessment.code)
            cloned_lo = lo_by_code.get(m.learning_outcome.code)
            if cloned_asmt and cloned_lo:
                AssessmentLOMapping.objects.create(
                    syllabus=revision,
                    assessment=cloned_asmt,
                    learning_outcome=cloned_lo,
                    weight=m.weight,
                    is_active=m.is_active,
                )

        if target_po_set_version is not None:
            target_po_by_code = {
                po.code: po
                for po in ProgramOutcome.objects.filter(
                    outcome_set__program_id=offering.program_id,
                    outcome_set__version=target_po_set_version,
                )
            }
            for m in syllabus.lo_po_mappings.select_related(
                "learning_outcome", "program_outcome"
            ).all():
                cloned_lo = lo_by_code.get(m.learning_outcome.code)
                target_po = target_po_by_code.get(m.program_outcome.code)
                if cloned_lo and target_po:
                    LOPOMapping.objects.create(
                        syllabus=revision,
                        learning_outcome=cloned_lo,
                        program_outcome=target_po,
                        weight=m.weight,
                        is_active=m.is_active,
                    )

        return revision

    @transaction.atomic
    def bind_active_po_set(self, *, syllabus) -> Syllabus:
        syllabus = (
            Syllabus.objects.select_for_update().select_related("offering").get(pk=syllabus.pk)
        )
        active = (
            ProgramOutcomeSet.objects.filter(
                program_id=syllabus.offering.program_id,
                status=ProgramOutcomeSet.Status.ACTIVE,
                effective_date__lte=timezone.localdate(),
            )
            .order_by("-effective_date")
            .first()
        )
        SyllabusValidator.validate_active_po_set_binding(syllabus, active)
        syllabus.po_set_version = active.version
        syllabus.save(update_fields=["po_set_version", "updated_at"])
        return syllabus

    # -- mapping matrices & validation -----------------------------------

    @transaction.atomic
    def replace_assessment_lo_matrix(
        self, *, syllabus, expected_revision: int, mappings: list[dict]
    ) -> Syllabus:
        syllabus = (
            Syllabus.objects.select_for_update().select_related("offering").get(pk=syllabus.pk)
        )
        self._editable(syllabus)
        if syllabus.mapping_revision != expected_revision:
            raise SyllabusMappingVersionConflict(syllabus.mapping_revision)

        normalized = SyllabusValidator.validate_assessment_lo_payload(
            syllabus=syllabus, mappings=mappings
        )
        for existing in list(syllabus.assessment_lo_mappings.all()):
            existing.delete()
        for item in normalized:
            AssessmentLOMapping.objects.create(
                syllabus=syllabus,
                assessment=item["assessment"],
                learning_outcome=item["learning_outcome"],
                weight=item["weight"],
                is_active=item["is_active"],
            )
        syllabus.mapping_revision += 1
        syllabus.save(update_fields=["mapping_revision", "updated_at"])
        return syllabus

    @transaction.atomic
    def replace_lo_po_matrix(
        self, *, syllabus, expected_revision: int, mappings: list[dict]
    ) -> Syllabus:
        syllabus = (
            Syllabus.objects.select_for_update().select_related("offering").get(pk=syllabus.pk)
        )
        self._editable(syllabus)
        if syllabus.mapping_revision != expected_revision:
            raise SyllabusMappingVersionConflict(syllabus.mapping_revision)

        normalized = SyllabusValidator.validate_lo_po_payload(syllabus=syllabus, mappings=mappings)
        for existing in list(syllabus.lo_po_mappings.all()):
            existing.delete()
        for item in normalized:
            LOPOMapping.objects.create(
                syllabus=syllabus,
                learning_outcome=item["learning_outcome"],
                program_outcome=item["program_outcome"],
                weight=item["weight"],
                is_active=item["is_active"],
            )
        syllabus.mapping_revision += 1
        syllabus.save(update_fields=["mapping_revision", "updated_at"])
        return syllabus

    def validate_mappings(self, *, syllabus) -> dict:
        return SyllabusValidator.validate_mappings(syllabus=syllabus)

    # -- draft-time mutation of children ---------------------------------

    @transaction.atomic
    def add_learning_outcome(self, *, syllabus, **data) -> LearningOutcome:
        syllabus = Syllabus.objects.select_for_update().get(pk=syllabus.pk)
        self._editable(syllabus)
        try:
            with transaction.atomic():
                return LearningOutcome.objects.create(syllabus=syllabus, **data)
        except IntegrityError as exc:
            raise ValidationError(
                "LO code or order already exists in this syllabus version."
            ) from exc

    @transaction.atomic
    def add_assessment(self, *, syllabus, **data) -> SyllabusAssessment:
        syllabus = Syllabus.objects.select_for_update().get(pk=syllabus.pk)
        self._editable(syllabus)
        SyllabusValidator.validate_assessment_points(data.get("max_points"))
        try:
            with transaction.atomic():
                return SyllabusAssessment.objects.create(syllabus=syllabus, **data)
        except IntegrityError as exc:
            raise ValidationError(
                "Assessment code or order already exists in this syllabus version."
            ) from exc

    @transaction.atomic
    def update_learning_outcome(self, *, instance, **data) -> LearningOutcome:
        instance.syllabus = Syllabus.objects.select_for_update().get(pk=instance.syllabus_id)
        self._editable(instance.syllabus)
        for field in self.MANAGED_FIELDS:
            if field in data:
                setattr(instance, field, data[field])
        try:
            with transaction.atomic():
                instance.save()
        except IntegrityError as exc:
            raise ValidationError(
                "LO code or order already exists in this syllabus version."
            ) from exc
        return instance

    @transaction.atomic
    def update_assessment(self, *, instance, **data) -> SyllabusAssessment:
        instance.syllabus = Syllabus.objects.select_for_update().get(pk=instance.syllabus_id)
        self._editable(instance.syllabus)
        for field in self.ASSESSMENT_FIELDS:
            if field in data:
                setattr(instance, field, data[field])
        SyllabusValidator.validate_assessment_points(instance.max_points)
        try:
            with transaction.atomic():
                instance.save()
        except IntegrityError as exc:
            raise ValidationError(
                "Assessment code or order already exists in this syllabus version."
            ) from exc
        return instance

    @transaction.atomic
    def delete_learning_outcome(self, *, instance) -> None:
        syllabus = Syllabus.objects.select_for_update().get(pk=instance.syllabus_id)
        self._editable(syllabus)
        instance.delete()

    @transaction.atomic
    def delete_assessment(self, *, instance) -> None:
        syllabus = Syllabus.objects.select_for_update().get(pk=instance.syllabus_id)
        self._editable(syllabus)
        instance.delete()

    def list_po_contributions(self, *, syllabus):
        return syllabus.po_contributions.select_related("program_outcome").order_by(
            "program_outcome__ordering", "created_at"
        )

    @transaction.atomic
    def set_po_contribution(
        self, *, syllabus, program_outcome, weight: int
    ) -> CoursePOContribution:
        syllabus = (
            Syllabus.objects.select_for_update().select_related("offering").get(pk=syllabus.pk)
        )
        po = (
            ProgramOutcome.objects.select_related("outcome_set")
            .filter(pk=getattr(program_outcome, "pk", program_outcome))
            .first()
        )
        SyllabusValidator.validate_po_contribution(syllabus, po, weight)
        existing = CoursePOContribution.objects.filter(
            syllabus=syllabus, program_outcome=po
        ).first()
        if existing is not None:
            existing.weight = weight
            existing.save(update_fields=["weight", "updated_at"])
            return existing
        try:
            with transaction.atomic():
                return CoursePOContribution.objects.create(
                    syllabus=syllabus,
                    program_outcome=po,
                    weight=weight,
                )
        except IntegrityError as exc:
            raise ValidationError(
                "A contribution weight for this program outcome already exists in this syllabus."
            ) from exc

    @transaction.atomic
    def delete_po_contribution(self, *, instance: CoursePOContribution) -> None:
        syllabus = Syllabus.objects.select_for_update().get(pk=instance.syllabus_id)
        self._editable(syllabus)
        instance.delete()

    # -- deletion ----------------------------------------------------------

    @transaction.atomic
    def remove_unused_draft(self, *, syllabus) -> Syllabus:
        """Retire an empty draft version; referenced versions stay untouched.


        Referenced means holding LO/assessment/po_contribution rows or having been approved.

        Referenced means holding LO/assessment/mapping rows or having been approved.

        Retirement keeps history (rows are hard-delete protected) and does not
        bump revisions because an empty draft never fed a calculation. Grade
        rows arrive with GRD-01 and will extend the referenced check there.
        """
        syllabus = (
            Syllabus.objects.select_for_update().select_related("offering").get(pk=syllabus.pk)
        )
        SyllabusValidator.validate_draft_removal(syllabus)
        Syllabus.objects.filter(pk=syllabus.pk).update(status=Syllabus.Status.RETIRED)
        syllabus.status = Syllabus.Status.RETIRED
        return syllabus

    @staticmethod
    def official_syllabus_for(offering):
        """Select compatible official inputs; calculation callers must use this boundary."""
        active = (
            ProgramOutcomeSet.objects.filter(
                program_id=offering.program_id,
                status=ProgramOutcomeSet.Status.ACTIVE,
                effective_date__lte=timezone.localdate(),
            )
            .order_by("-effective_date")
            .first()
        )
        if not active:
            raise ValidationError("No active PO-set exists for this program.")
        syllabus = offering.syllabi.filter(
            status=Syllabus.Status.APPROVED, po_set_version=active.version
        ).first()
        if not syllabus:
            raise ValidationError("No approved syllabus matches the active PO-set version.")
        return syllabus


official_syllabus_for = SyllabusService.official_syllabus_for
