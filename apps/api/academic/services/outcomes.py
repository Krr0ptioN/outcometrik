from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .. import scoping
from ..models import Program, ProgramOutcome, ProgramOutcomeSet
from .base import AcademicService

OUTCOME_TEXT_FIELDS = ("code", "label", "description", "source_url")


def _scoped_programs(actor):
    return scoping.scope_programs(actor, Program.objects.all())


def validate_activation(outcome_set, effective_date):
    if outcome_set.status != ProgramOutcomeSet.Status.DRAFT:
        raise ValidationError({"status": "Only a draft set can be activated."})
    if effective_date is None:
        raise ValidationError({"effective_date": "Required for activation."})
    if not outcome_set.source_reference.strip():
        raise ValidationError({"source_reference": "Required for activation."})

    outcomes = list(outcome_set.outcomes.order_by("ordering"))
    if not outcomes:
        raise ValidationError({"outcomes": "A set needs at least one outcome."})
    for outcome in outcomes:
        for field in OUTCOME_TEXT_FIELDS:
            if not str(getattr(outcome, field)).strip():
                raise ValidationError({"outcomes": f"{outcome.code or '?'}: {field} is required."})
    if [o.ordering for o in outcomes] != list(range(1, len(outcomes) + 1)):
        raise ValidationError({"outcomes": "Ordering must be 1..N with no gaps."})

    latest = (
        ProgramOutcomeSet.objects.filter(
            program_id=outcome_set.program_id, status=ProgramOutcomeSet.Status.ACTIVE
        )
        .exclude(pk=outcome_set.pk)
        .order_by("-effective_date")
        .first()
    )
    if latest and effective_date <= latest.effective_date:
        raise ValidationError(
            {"effective_date": "Must be later than the current active set's effective date."}
        )


def activate_set(outcome_set, actor, effective_date=None):
    """Domain operation. Callers must authorize first (the seed command is trusted)."""
    with transaction.atomic():
        Program.objects.select_for_update().get(pk=outcome_set.program_id)
        locked = ProgramOutcomeSet.objects.select_for_update().get(pk=outcome_set.pk)
        effective_date = effective_date or locked.effective_date
        validate_activation(locked, effective_date)
        locked.effective_date = effective_date
        locked.status = ProgramOutcomeSet.Status.ACTIVE
        locked.activated_at = timezone.now()
        locked.activated_by = actor
        locked.save()
    return locked


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
        if instance.status == ProgramOutcomeSet.Status.ACTIVE:
            raise ValidationError("An active set is immutable. Create a new version.")
        super().validate_update(instance, data)

    @transaction.atomic
    def activate(self, *, instance, effective_date=None):
        self.check_access(self.actor, "program.manage", instance.program_id)
        return activate_set(instance, self.actor, effective_date)


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
        self._check(data["outcome_set"], data)

    def validate_update(self, instance, data):
        if "order" in data and "ordering" not in data:
            data["ordering"] = data.pop("order")
        if "source_reference" in data and "source_url" not in data:
            data["source_url"] = data.pop("source_reference")
        super().validate_update(instance, data)
        self._check(instance.outcome_set, data, exclude_pk=instance.pk)

    @staticmethod
    def _check(outcome_set, data, exclude_pk=None):
        if outcome_set.status != ProgramOutcomeSet.Status.DRAFT:
            raise ValidationError("Outcomes of an active set are immutable. Create a new version.")
        siblings = outcome_set.outcomes.exclude(pk=exclude_pk)
        for field in ("code", "ordering"):
            if field in data and siblings.filter(**{field: data[field]}).exists():
                raise ValidationError({field: "Must be unique within the set."})
