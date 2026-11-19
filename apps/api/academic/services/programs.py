from typing import Any

from access.policy import AuthorizationService
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from wireup import injectable

from .. import scoping
from ..models import Program, ProgramCourse, ProgramMembership


def _handle_integrity_error(exc: IntegrityError) -> None:
    raise ValidationError("This academic record conflicts with an existing record.") from exc


@injectable
class ProgramService:
    """Manages academic programs with explicit dependency injection and actor scoping."""

    model = Program
    immutable_fields = ("department",)

    def __init__(self, auth_service: AuthorizationService, *, actor: Any = None):
        self.auth_service = auth_service
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Program.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Program.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_programs(effective_actor, queryset)

    @transaction.atomic
    def create(self, **data) -> Program:
        try:
            return Program.objects.create(**data)
        except IntegrityError as exc:
            _handle_integrity_error(exc)

    @transaction.atomic
    def update(self, *, instance: Program, **data) -> Program:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            _handle_integrity_error(exc)
        return instance


@injectable
class ProgramCourseService:
    """Manages course-program links with explicit dependency injection and validation."""

    model = ProgramCourse
    immutable_fields = ("program", "course")

    def __init__(self, auth_service: AuthorizationService, *, actor: Any = None):
        self.auth_service = auth_service
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(ProgramCourse.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = ProgramCourse.objects.all()
        effective_actor = actor if actor is not None else self.actor
        programs = scoping.scope_programs(effective_actor, Program.objects.all())
        return queryset.filter(program__in=programs)

    @staticmethod
    def _validate_window(effective_from, effective_to):
        if effective_to and effective_to < effective_from:
            raise ValidationError({"effective_to": "Must not be before effective_from."})

    @transaction.atomic
    def create(self, **data) -> ProgramCourse:
        self._validate_window(data["effective_from"], data.get("effective_to"))
        try:
            return ProgramCourse.objects.create(**data)
        except IntegrityError as exc:
            _handle_integrity_error(exc)

    @transaction.atomic
    def update(self, *, instance: ProgramCourse, **data) -> ProgramCourse:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        starts = data.get("effective_from", instance.effective_from)
        ends = data.get("effective_to", instance.effective_to)
        self._validate_window(starts, ends)
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            _handle_integrity_error(exc)
        return instance


@injectable
class ProgramMembershipService:
    """Manages student program memberships with explicit dependency injection."""

    model = ProgramMembership
    immutable_fields = ("program", "user")

    def __init__(self, auth_service: AuthorizationService, *, actor: Any = None):
        self.auth_service = auth_service
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(ProgramMembership.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = ProgramMembership.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_memberships(effective_actor, queryset)

    @transaction.atomic
    def create(self, **data) -> ProgramMembership:
        try:
            return ProgramMembership.objects.create(**data)
        except IntegrityError as exc:
            _handle_integrity_error(exc)

    @transaction.atomic
    def update(self, *, instance: ProgramMembership, **data) -> ProgramMembership:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            _handle_integrity_error(exc)
        return instance
