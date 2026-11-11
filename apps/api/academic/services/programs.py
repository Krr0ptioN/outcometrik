from django.core.exceptions import ValidationError

from .. import scoping
from ..models import Program, ProgramCourse, ProgramMembership
from .base import AcademicService


class ProgramService(AcademicService):
    model = Program
    immutable_fields = ("department",)

    def visible_queryset(self, queryset):
        return scoping.scope_programs(self.actor, queryset)

    def create_access(self, data):
        return "program.manage", data["department"].institution_id

    def update_access(self, instance):
        return "program.manage", instance.pk


class ProgramCourseService(AcademicService):
    model = ProgramCourse
    immutable_fields = ("program", "course")

    def visible_queryset(self, queryset):
        programs = scoping.scope_programs(self.actor, Program.objects.all())
        return queryset.filter(program__in=programs)

    def create_access(self, data):
        return "program.manage", data["program"].pk

    def update_access(self, instance):
        return "program.manage", instance.program_id

    def validate_create(self, data):
        self._validate_window(data["effective_from"], data.get("effective_to"))

    def validate_update(self, instance, data):
        super().validate_update(instance, data)
        starts = data.get("effective_from", instance.effective_from)
        ends = data.get("effective_to", instance.effective_to)
        self._validate_window(starts, ends)

    @staticmethod
    def _validate_window(effective_from, effective_to):
        if effective_to and effective_to < effective_from:
            raise ValidationError({"effective_to": "Must not be before effective_from."})


class ProgramMembershipService(AcademicService):
    model = ProgramMembership
    immutable_fields = ("program", "user")

    def visible_queryset(self, queryset):
        return scoping.scope_memberships(self.actor, queryset)

    def create_access(self, data):
        return "program.manage", data["program"].pk

    def update_access(self, instance):
        return "program.manage", instance.program_id
