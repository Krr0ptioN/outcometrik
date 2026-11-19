from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .. import scoping
from ..models import Program, ProgramOutcome, ProgramOutcomeSet
from .base import AcademicService
from .outcome_validation import ProgramOutcomeSetValidator


def _scoped_programs(actor):
    return scoping.scope_programs(actor, Program.objects.all())


class ProgramOutcomeSetService(AcademicService):
    model = ProgramOutcomeSet
    immutable_fields = ("program", "version")

    def visible_queryset(self, queryset):
        return queryset.filter(program__in=_scoped_programs(self.actor)).prefetch_related(
            "outcomes"
        )

    def create_access(self, data):
        return "program.manage", data["program"].pk

    def update_access(self, instance):
        return "program.manage", instance.program_id

    def validate_create(self, data):
        last = ProgramOutcomeSet.objects.filter(program=data["program"]).aggregate(
            m=Max("version")
        )["m"]
        data["version"] = data.get("version") or ((last or 0) + 1)

    def validate_update(self, instance, data):
        ProgramOutcomeSetValidator.validate_set_update(instance, data)
        super().validate_update(instance, data)

    @transaction.atomic
    def activate(self, *, instance, effective_date=None, authorize=True):
        """Activate a program outcome set version, enforcing row locks and domain invariants."""
        if authorize:
            self.check_access(self.actor, "program.manage", instance.program_id)
        Program.objects.select_for_update().get(pk=instance.program_id)
        locked = ProgramOutcomeSet.objects.select_for_update().get(pk=instance.pk)
        effective_date = effective_date or locked.effective_date
        ProgramOutcomeSetValidator.validate_activation(locked, effective_date)
        locked.effective_date = effective_date
        locked.status = ProgramOutcomeSet.Status.ACTIVE
        locked.activated_at = timezone.now()
        locked.activated_by = self.actor
        locked.save()
        return locked


class ProgramOutcomeService(AcademicService):
    model = ProgramOutcome
    immutable_fields = ("outcome_set",)

    def visible_queryset(self, queryset):
        return queryset.filter(outcome_set__program__in=_scoped_programs(self.actor))

    def create_access(self, data):
        outcome_set = (
            data.get("outcome_set") or getattr(self, "instance", None) and self.instance.outcome_set
        )
        return "program.manage", outcome_set.program_id

    def update_access(self, instance):
        return "program.manage", instance.outcome_set.program_id

    def validate_create(self, data):
        if "order" in data and "ordering" not in data:
            data["ordering"] = data.pop("order")
        if "source_reference" in data and "source_url" not in data:
            data["source_url"] = data.pop("source_reference")
        ProgramOutcomeSetValidator.validate_mutation(data["outcome_set"], data)

    def validate_update(self, instance, data):
        if "order" in data and "ordering" not in data:
            data["ordering"] = data.pop("order")
        if "source_reference" in data and "source_url" not in data:
            data["source_url"] = data.pop("source_reference")
        super().validate_update(instance, data)
        ProgramOutcomeSetValidator.validate_mutation(
            instance.outcome_set, data, exclude_pk=instance.pk
        )
