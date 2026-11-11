from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .. import scoping
from ..access_control import require
from ..models import Assessment, CourseOffering, LearningOutcome, Syllabus
from .base import AcademicService
from .offerings import bump_revisions

MANAGED_FIELDS = ("code", "description", "order")
ASSESSMENT_FIELDS = ("code", "kind", "order", "is_required", "is_active", "max_points")


def _lock_offering_row(offering_id):
    return CourseOffering.objects.select_for_update().get(pk=offering_id)


class SyllabusService(AcademicService):
    """Versioned syllabus lifecycle: draft, approve, revise.

    Draft configuration is editable; approval locks a version forever, and a
    revision clones the prior version into a new draft. Single-draft and
    single-official-version invariants are enforced with database constraints;
    authorization is delegated to the scoped access policy (``syllabus.draft``
    at the offering scope, ``syllabus.approve`` at the program scope).
    """

    model = Syllabus
    immutable_fields = ("offering", "version", "status")

    def visible_queryset(self, queryset):
        return scoping.scope_syllabi(self.actor, queryset)

    def create_access(self, data):
        return "syllabus.draft", data["offering"].pk

    def update_access(self, instance):
        return "syllabus.draft", instance.offering_id

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _editable(syllabus):
        if syllabus.status != Syllabus.Status.DRAFT:
            raise ValidationError("This syllabus version is locked; create a revision instead.")
        return syllabus

    # -- lifecycle -------------------------------------------------------

    @transaction.atomic
    def create(self, *, offering, po_set_version=None):
        offering = _lock_offering_row(offering.pk)
        require(self.actor, "syllabus.draft", offering.pk)
        blocked = offering.syllabi.filter(
            status__in=(Syllabus.Status.DRAFT, Syllabus.Status.APPROVED)
        ).exists()
        if blocked:
            raise ValidationError(
                "A draft or approved syllabus already exists for this offering;"
                " revise the approved version or retire the draft first."
            )
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
    def approve(self, *, syllabus):
        # Lock every version row of this offering so no concurrent approve/create slips in.
        offering_versions = Syllabus.objects.select_for_update().filter(
            offering_id=syllabus.offering_id
        )
        syllabus = offering_versions.select_related("offering").get(pk=syllabus.pk)
        offering = syllabus.offering
        # Approval authority is program-scoped: coordinators approve their program's
        # offerings. Instructors hold only offering-scoped roles and cannot approve.
        require(self.actor, "syllabus.approve", offering.program_id)
        self._editable(syllabus)
        if not syllabus.learning_outcomes.exists() or not syllabus.assessments.exists():
            raise ValidationError("A syllabus version needs at least one LO and one assessment.")
        # Supersede: a newer approved version retires the previously official one so
        # the single-official-version constraint holds across the whole history.
        offering_versions.exclude(pk=syllabus.pk).filter(
            status=Syllabus.Status.APPROVED
        ).update(status=Syllabus.Status.RETIRED)
        # Compatibility with the offering's active PO set is validated here once
        # OUT-01 introduces versioned PO sets; po_set_version records the binding.
        syllabus.status = Syllabus.Status.APPROVED
        syllabus.approved_by = self.actor
        syllabus.approved_at = timezone.now()
        try:
            with transaction.atomic():
                syllabus.save(
                    update_fields=["status", "approved_by", "approved_at", "updated_at"]
                )
        except IntegrityError as exc:
            raise ValidationError(
                "Another syllabus version is already approved for this offering."
            ) from exc
        # Activating a syllabus changes calculation inputs; detect stale results.
        bump_revisions(program_id=offering.program_id, offering_id=offering.pk)
        return syllabus

    @transaction.atomic
    def revise(self, *, syllabus):
        syllabus = Syllabus.objects.select_for_update().select_related("offering").get(
            pk=syllabus.pk
        )
        offering = syllabus.offering
        require(self.actor, "syllabus.draft", offering.pk)
        if syllabus.status != Syllabus.Status.APPROVED:
            raise ValidationError("Only an approved syllabus version can be revised.")
        if offering.syllabi.filter(status=Syllabus.Status.DRAFT).exists():
            raise ValidationError("A draft revision already exists for this offering.")
        version = offering.syllabi.count() + 1
        revision = Syllabus(
            offering=offering,
            version=version,
            status=Syllabus.Status.DRAFT,
            po_set_version=syllabus.po_set_version,
        )
        try:
            with transaction.atomic():
                revision.save()
        except IntegrityError as exc:
            raise ValidationError("A conflicting draft revision already exists.") from exc
        for lo in syllabus.learning_outcomes.all().order_by("order"):
            LearningOutcome.objects.create(
                syllabus=revision, code=lo.code, description=lo.description, order=lo.order
            )
        for a in syllabus.assessments.all().order_by("order"):
            Assessment.objects.create(
                syllabus=revision,
                code=a.code,
                kind=a.kind,
                order=a.order,
                is_required=a.is_required,
                is_active=a.is_active,
                max_points=a.max_points,
            )
        return revision

    # -- draft-time mutation of children ---------------------------------

    def add_learning_outcome(self, *, syllabus, **data):
        require(self.actor, "syllabus.draft", syllabus.offering_id)
        self._editable(syllabus)
        try:
            with transaction.atomic():
                return LearningOutcome.objects.create(syllabus=syllabus, **data)
        except IntegrityError as exc:
            raise ValidationError("LO code or order already exists in this syllabus version.") from exc

    def add_assessment(self, *, syllabus, **data):
        require(self.actor, "syllabus.draft", syllabus.offering_id)
        self._editable(syllabus)
        if data.get("max_points") is not None and data["max_points"] <= 0:
            raise ValidationError({"max_points": "Maximum points must be greater than zero."})
        try:
            with transaction.atomic():
                return Assessment.objects.create(syllabus=syllabus, **data)
        except IntegrityError as exc:
            raise ValidationError(
                "Assessment code or order already exists in this syllabus version."
            ) from exc

    def update_learning_outcome(self, *, instance, **data):
        require(self.actor, "syllabus.draft", instance.syllabus.offering_id)
        self._editable(instance.syllabus)
        for field in MANAGED_FIELDS:
            if field in data:
                setattr(instance, field, data[field])
        try:
            with transaction.atomic():
                instance.save()
        except IntegrityError as exc:
            raise ValidationError("LO code or order already exists in this syllabus version.") from exc
        return instance

    def update_assessment(self, *, instance, **data):
        require(self.actor, "syllabus.draft", instance.syllabus.offering_id)
        self._editable(instance.syllabus)
        for field in ASSESSMENT_FIELDS:
            if field in data:
                setattr(instance, field, data[field])
        if instance.max_points is not None and instance.max_points <= 0:
            raise ValidationError({"max_points": "Maximum points must be greater than zero."})
        try:
            with transaction.atomic():
                instance.save()
        except IntegrityError as exc:
            raise ValidationError(
                "Assessment code or order already exists in this syllabus version."
            ) from exc
        return instance

    # -- deletion ----------------------------------------------------------

    @transaction.atomic
    def remove_unused_draft(self, *, syllabus):
        """Retire an empty draft version; referenced versions stay untouched.

        Referenced means holding LO/assessment rows or having been approved.
        Retirement keeps history (rows are hard-delete protected) and does not
        bump revisions because an empty draft never fed a calculation. Grade
        rows arrive with GRD-01 and will extend the referenced check there.
        """
        syllabus = Syllabus.objects.select_for_update().select_related("offering").get(
            pk=syllabus.pk
        )
        require(self.actor, "syllabus.draft", syllabus.offering_id)
        self._editable(syllabus)
        if syllabus.learning_outcomes.exists() or syllabus.assessments.exists():
            raise ValidationError(
                "This syllabus version holds configuration; revise instead of removing it."
            )
        Syllabus.objects.filter(pk=syllabus.pk).update(status=Syllabus.Status.RETIRED)
        syllabus.status = Syllabus.Status.RETIRED
        return syllabus
