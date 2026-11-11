from access.models import Role, Scope
from access.services import assign
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F

from .. import scoping
from ..access_control import require
from ..models import CourseOffering, InstructorAssignment, Program
from .base import AcademicService


def bump_revisions(*, program_id, offering_id=None):
    Program.objects.filter(pk=program_id).update(input_revision=F("input_revision") + 1)
    if offering_id is not None:
        CourseOffering.objects.filter(pk=offering_id).update(input_revision=F("input_revision") + 1)


class CourseOfferingService(AcademicService):
    model = CourseOffering
    immutable_fields = ("program", "course", "term")

    def visible_queryset(self, queryset):
        return scoping.scope_offerings(self.actor, queryset)

    def create_access(self, data):
        return "offering.manage", data["program"].pk

    def update_access(self, instance):
        return "offering.manage", instance.pk

    @transaction.atomic
    def create(self, *, program, course, term, section, status=CourseOffering.Status.ACTIVE):
        require(self.actor, "offering.manage", program.pk)
        offering = CourseOffering(
            program=program, course=course, term=term, section=section, status=status
        )
        try:
            offering.save()
        except IntegrityError as exc:
            raise ValidationError("This offering already exists.") from exc
        if offering.status == CourseOffering.Status.ACTIVE:
            bump_revisions(program_id=program.pk)
        return offering


class InstructorAssignmentService(AcademicService):
    model = InstructorAssignment
    immutable_fields = ("offering", "user", "assignment_role")

    def visible_queryset(self, queryset):
        return scoping.scope_assignments(self.actor, queryset)

    def create_access(self, data):
        return "access.manage", data["offering"].pk

    def update_access(self, instance):
        return "access.manage", instance.offering_id

    @transaction.atomic
    def create(self, *, offering, user, assignment_role):
        require(self.actor, "access.manage", offering.pk)
        if not user.is_active:
            raise ValidationError("The instructor account must be active.")
        assignment, _ = InstructorAssignment.objects.get_or_create(
            offering=offering, user=user, defaults={"assignment_role": assignment_role}
        )
        if assignment_role == InstructorAssignment.Role.INSTRUCTOR:
            assign(
                actor=self.actor,
                user=user,
                scope=Scope.objects.get(pk=offering.pk),
                role=Role.objects.get(pk="instructor"),
            )
        return assignment
