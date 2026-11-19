from typing import Any

from access.policy import AuthorizationService
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from wireup import injectable

from .. import scoping
from ..models import Program, ProgramOutcome, ProgramOutcomeSet
from .outcome_validation import ProgramOutcomeSetValidator


@injectable
class ProgramOutcomeSetService:
    """Manages program outcome sets with explicit dependency injection and actor scoping."""

    model = ProgramOutcomeSet
    immutable_fields = ("program", "version")

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def _scoped_programs(self, actor: Any = None):
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_programs(effective_actor, Program.objects.all())

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(ProgramOutcomeSet.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = ProgramOutcomeSet.objects.all()
        return queryset.filter(program__in=self._scoped_programs(actor)).prefetch_related(
            "outcomes"
        )

    @transaction.atomic
    def create(self, **data) -> ProgramOutcomeSet:
        program = data["program"]
        last = ProgramOutcomeSet.objects.filter(program=program).aggregate(m=Max("version"))["m"]
        data["version"] = data.get("version") or ((last or 0) + 1)
        try:
            return ProgramOutcomeSet.objects.create(**data)
        except IntegrityError as exc:
            raise ValidationError("This outcome set conflicts with an existing record.") from exc

    @transaction.atomic
    def update(self, *, instance: ProgramOutcomeSet, **data) -> ProgramOutcomeSet:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        ProgramOutcomeSetValidator.validate_set_update(instance, data)
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            raise ValidationError("This outcome set conflicts with an existing record.") from exc
        return instance

    @transaction.atomic
    def activate(
        self,
        *,
        instance: ProgramOutcomeSet,
        effective_date=None,
        actor: Any = None,
        authorize: bool = True,
    ) -> ProgramOutcomeSet:
        """Activate a program outcome set version, enforcing row locks and domain invariants."""
        effective_actor = actor or self.actor
        Program.objects.select_for_update().get(pk=instance.program_id)
        locked = ProgramOutcomeSet.objects.select_for_update().get(pk=instance.pk)
        effective_date = effective_date or locked.effective_date
        ProgramOutcomeSetValidator.validate_activation(locked, effective_date)
        locked.effective_date = effective_date
        locked.status = ProgramOutcomeSet.Status.ACTIVE
        locked.activated_at = timezone.now()
        locked.activated_by = effective_actor
        locked.save()
        return locked


@injectable
class ProgramOutcomeService:
    """Manages individual program outcomes with explicit dependency injection and actor scoping."""

    model = ProgramOutcome
    immutable_fields = ("outcome_set",)

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def _scoped_programs(self, actor: Any = None):
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_programs(effective_actor, Program.objects.all())

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(ProgramOutcome.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("ordering", "created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = ProgramOutcome.objects.all()
        return queryset.filter(outcome_set__program__in=self._scoped_programs(actor))

    @transaction.atomic
    def create(self, **data) -> ProgramOutcome:
        if "order" in data and "ordering" not in data:
            data["ordering"] = data.pop("order")
        if "source_reference" in data and "source_url" not in data:
            data["source_url"] = data.pop("source_reference")
        ProgramOutcomeSetValidator.validate_mutation(data["outcome_set"], data)
        try:
            return ProgramOutcome.objects.create(**data)
        except IntegrityError as exc:
            raise ValidationError("This outcome conflicts with an existing record.") from exc

    @transaction.atomic
    def update(self, *, instance: ProgramOutcome, **data) -> ProgramOutcome:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        if "order" in data and "ordering" not in data:
            data["ordering"] = data.pop("order")
        if "source_reference" in data and "source_url" not in data:
            data["source_url"] = data.pop("source_reference")
        ProgramOutcomeSetValidator.validate_mutation(
            instance.outcome_set, data, exclude_pk=instance.pk
        )
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            raise ValidationError("This outcome conflicts with an existing record.") from exc
        return instance
