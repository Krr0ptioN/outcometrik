from typing import Any

from access.models import Role, Scope
from access.policy import AuthorizationService
from access.services import assign
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from wireup import injectable

from .. import scoping
from ..models import CourseOffering, InstructorAssignment
from .revisions import RevisionTracker


def _handle_integrity_error(exc: IntegrityError) -> None:
    raise ValidationError("This offering already exists.") from exc


@injectable
class CourseOfferingService:
    """Manages course offerings with explicit dependency injection and actor scoping."""

    model = CourseOffering
    immutable_fields = ("program", "course", "term")

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(CourseOffering.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = CourseOffering.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_offerings(effective_actor, queryset)

    @transaction.atomic
    def create(
        self,
        *,
        program,
        course,
        term,
        section,
        status=CourseOffering.Status.ACTIVE,
        **extra,
    ) -> CourseOffering:
        offering = CourseOffering(
            program=program, course=course, term=term, section=section, status=status
        )
        try:
            offering.save()
        except IntegrityError as exc:
            raise ValidationError("This offering already exists.") from exc
        if offering.status == CourseOffering.Status.ACTIVE:
            RevisionTracker.bump(program_id=program.pk)
        return offering

    @transaction.atomic
    def update(self, *, instance: CourseOffering, **data) -> CourseOffering:
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
class InstructorAssignmentService:
    """Manages instructor assignments with explicit dependency injection and actor scoping."""

    model = InstructorAssignment
    immutable_fields = ("offering", "user", "assignment_role")

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(InstructorAssignment.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = InstructorAssignment.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_assignments(effective_actor, queryset)

    @transaction.atomic
    def create(self, *, offering, user, assignment_role, **extra) -> InstructorAssignment:
        effective_actor = extra.get("actor", self.actor)
        if not user.is_active:
            raise ValidationError("The instructor account must be active.")
        assignment, _ = InstructorAssignment.objects.get_or_create(
            offering=offering, user=user, defaults={"assignment_role": assignment_role}
        )
        if assignment_role == InstructorAssignment.Role.INSTRUCTOR:
            assign(
                actor=effective_actor,
                user=user,
                scope=Scope.objects.get(pk=offering.pk),
                role=Role.objects.get(pk="instructor"),
            )
        return assignment

    @transaction.atomic
    def update(self, *, instance: InstructorAssignment, **data) -> InstructorAssignment:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            raise ValidationError("This assignment conflicts with an existing record.") from exc
        return instance
