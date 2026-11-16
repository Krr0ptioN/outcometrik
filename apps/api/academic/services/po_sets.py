from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .. import scoping
from ..access_control import require
from ..models import CourseOffering, Program, ProgramOutcome, ProgramOutcomeSet
from .base import AcademicService


class ProgramOutcomeSetService(AcademicService):
    model = ProgramOutcomeSet

    def visible_queryset(self, queryset):
        return queryset.filter(
            program__in=scoping.scope_programs(self.actor, Program.objects.all())
        )

    def create_access(self, data):
        return "syllabus.approve", data["program"].pk

    @transaction.atomic
    def activate(self, *, instance):
        Program.objects.select_for_update().get(pk=instance.program_id)
        require(self.actor, "syllabus.approve", instance.program_id)
        instance = ProgramOutcomeSet.objects.select_for_update().get(pk=instance.pk)
        if instance.effective_date > timezone.localdate():
            raise ValidationError("The PO set effective date must not be in the future.")
        if instance.active:
            raise ValidationError("This PO set is already active.")
        if instance.activated_at:
            raise ValidationError("A previously activated PO set cannot be reactivated.")
        outcomes = list(instance.outcomes.order_by("order"))
        if len(outcomes) != 11 or any(
            outcome.code != f"PO{index}"
            or outcome.order != index
            or not outcome.label.strip()
            or not outcome.description.strip()
            or not outcome.source_reference.strip()
            for index, outcome in enumerate(outcomes, 1)
        ):
            raise ValidationError(
                "Activation requires complete, ordered outcomes PO1 through PO11."
            )
        ProgramOutcomeSet.objects.filter(program_id=instance.program_id, active=True).update(
            active=False
        )
        instance.active = True
        instance.activated_by = self.actor
        instance.activated_at = timezone.now()
        instance.save(update_fields=["active", "activated_by", "activated_at", "updated_at"])
        Program.objects.filter(pk=instance.program_id).update(
            input_revision=F("input_revision") + 1
        )
        CourseOffering.objects.filter(program_id=instance.program_id).update(
            input_revision=F("input_revision") + 1
        )
        return instance

    @transaction.atomic
    def save_outcome(self, *, po_set, outcome=None, **data):
        Program.objects.select_for_update().get(pk=po_set.program_id)
        require(self.actor, "syllabus.approve", po_set.program_id)
        po_set = ProgramOutcomeSet.objects.select_for_update().get(pk=po_set.pk)
        if po_set.activated_at:
            raise ValidationError("Activated PO sets cannot be edited.")
        if outcome is None:
            outcome = ProgramOutcome(po_set=po_set)
        elif outcome.po_set_id != po_set.pk:
            raise ValidationError("Outcome belongs to a different PO set.")
        for field, value in data.items():
            setattr(outcome, field, value)
        if outcome.order not in range(1, 12) or outcome.code != f"PO{outcome.order}":
            raise ValidationError("Outcome code and order must match PO1 through PO11.")
        if not all(
            value and value.strip()
            for value in (outcome.label, outcome.description, outcome.source_reference)
        ):
            raise ValidationError("Outcome label, description, and source are required.")
        try:
            with transaction.atomic():
                outcome.save()
        except IntegrityError as exc:
            raise ValidationError("Outcome code or order already exists in this PO set.") from exc
        return outcome
