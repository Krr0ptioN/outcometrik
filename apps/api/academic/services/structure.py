from access.models import Scope
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .. import scoping
from ..models import AcademicTerm, Course, Department, Institution
from .base import AcademicService


class InstitutionService(AcademicService):
    model = Institution

    def visible_queryset(self, queryset):
        return scoping.scope_institutions(self.actor, queryset)

    def update_access(self, instance):
        return "access.manage", instance.pk

    @transaction.atomic
    def create(self, **data):
        scope = Scope.objects.filter(kind=Scope.Kind.INSTITUTION, label=data["name"]).first()
        if scope is None:
            raise PermissionDenied("Create institution scopes through trusted bootstrap.")
        self.check_access(self.actor, "access.manage", scope.pk)
        return Institution.objects.create(pk=scope.pk, **data)


class DepartmentService(AcademicService):
    model = Department
    immutable_fields = ("institution",)

    def visible_queryset(self, queryset):
        return scoping.scope_departments(self.actor, queryset)

    def create_access(self, data):
        return "access.manage", data["institution"].pk

    def update_access(self, instance):
        return "access.manage", instance.institution_id


class AcademicTermService(AcademicService):
    model = AcademicTerm
    immutable_fields = ("institution", "year", "season")

    def visible_queryset(self, queryset):
        return scoping.scope_terms(self.actor, queryset)

    def create_access(self, data):
        return "access.manage", data["institution"].pk

    def update_access(self, instance):
        return "access.manage", instance.institution_id

    def validate_create(self, data):
        self._validate_dates(data["starts_at"], data["ends_at"])

    def validate_update(self, instance, data):
        super().validate_update(instance, data)
        starts = data.get("starts_at", instance.starts_at)
        ends = data.get("ends_at", instance.ends_at)
        self._validate_dates(starts, ends)

    @staticmethod
    def _validate_dates(starts_at, ends_at):
        if ends_at <= starts_at:
            raise ValidationError({"ends_at": "Must be after starts_at."})


class CourseService(AcademicService):
    model = Course
    immutable_fields = ("home_department", "code")

    def visible_queryset(self, queryset):
        return scoping.scope_courses(self.actor, queryset)

    def create_access(self, data):
        return "access.manage", data["home_department"].institution_id

    def update_access(self, instance):
        return "access.manage", instance.home_department.institution_id
