from typing import Any

from access.models import Scope
from access.policy import AuthorizationService
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from wireup import injectable

from .. import scoping
from ..models import AcademicTerm, Course, Department, Institution


def _handle_integrity_error(exc: IntegrityError) -> None:
    raise ValidationError("This academic record conflicts with an existing record.") from exc


@injectable
class InstitutionService:
    """Manages institutions with explicit dependency injection and actor scoping."""

    model = Institution

    def __init__(self, auth_service: AuthorizationService, *, actor: Any = None):
        self.auth_service = auth_service
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Institution.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Institution.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_institutions(effective_actor, queryset)

    @transaction.atomic
    def create(self, **data) -> Institution:
        name = data.get("name")
        scope = Scope.objects.filter(kind=Scope.Kind.INSTITUTION, label=name).first()
        if scope is None:
            raise ValidationError(
                {"name": "Institution scope must exist prior to creating an institution record."}
            )
        try:
            return Institution.objects.create(pk=scope.pk, **data)
        except IntegrityError as exc:
            _handle_integrity_error(exc)

    @transaction.atomic
    def update(self, *, instance: Institution, **data) -> Institution:
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            _handle_integrity_error(exc)
        return instance


@injectable
class DepartmentService:
    """Manages departments with explicit dependency injection and actor scoping."""

    model = Department
    immutable_fields = ("institution",)

    def __init__(self, auth_service: AuthorizationService, *, actor: Any = None):
        self.auth_service = auth_service
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Department.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Department.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_departments(effective_actor, queryset)

    @transaction.atomic
    def create(self, **data) -> Department:
        try:
            return Department.objects.create(**data)
        except IntegrityError as exc:
            _handle_integrity_error(exc)

    @transaction.atomic
    def update(self, *, instance: Department, **data) -> Department:
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
class AcademicTermService:
    """Manages academic terms with explicit dependency injection and actor scoping."""

    model = AcademicTerm
    immutable_fields = ("institution", "year", "season")

    def __init__(self, auth_service: AuthorizationService, *, actor: Any = None):
        self.auth_service = auth_service
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(AcademicTerm.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = AcademicTerm.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_terms(effective_actor, queryset)

    @staticmethod
    def _validate_dates(starts_at, ends_at):
        if ends_at <= starts_at:
            raise ValidationError({"ends_at": "Must be after starts_at."})

    @transaction.atomic
    def create(self, **data) -> AcademicTerm:
        self._validate_dates(data["starts_at"], data["ends_at"])
        try:
            return AcademicTerm.objects.create(**data)
        except IntegrityError as exc:
            _handle_integrity_error(exc)

    @transaction.atomic
    def update(self, *, instance: AcademicTerm, **data) -> AcademicTerm:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        starts = data.get("starts_at", instance.starts_at)
        ends = data.get("ends_at", instance.ends_at)
        self._validate_dates(starts, ends)
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            _handle_integrity_error(exc)
        return instance


@injectable
class CourseService:
    """Manages courses with explicit dependency injection and actor scoping."""

    model = Course
    immutable_fields = ("home_department", "code")

    def __init__(self, auth_service: AuthorizationService, *, actor: Any = None):
        self.auth_service = auth_service
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Course.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Course.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_courses(effective_actor, queryset)

    @transaction.atomic
    def create(self, **data) -> Course:
        try:
            return Course.objects.create(**data)
        except IntegrityError as exc:
            _handle_integrity_error(exc)

    @transaction.atomic
    def update(self, *, instance: Course, **data) -> Course:
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
