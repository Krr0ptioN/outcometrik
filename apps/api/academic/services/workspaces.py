from access.identity import user_data
from access.models import DirectCapabilityGrant, RoleAssignment, Scope
from access.policy import authorization
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .. import scoping
from ..models import CourseOffering, Enrollment, Program, ProgramMembership


class WorkspaceService:
    def __init__(self, *, actor):
        self.actor = actor

    def instructor_offerings(self):
        assignments = RoleAssignment.objects.filter(
            user=self.actor, role_id="instructor", revoked_at__isnull=True
        )
        if not assignments.exists():
            raise PermissionDenied("Instructor access is required.")
        grant_scopes = DirectCapabilityGrant.objects.filter(
            user=self.actor, capability_id="grades.view", revoked_at__isnull=True
        ).values_list("scope_id", flat=True)
        scopes = Scope.objects.filter(
            Q(pk__in=assignments.values_list("scope_id", flat=True)) | Q(pk__in=grant_scopes),
            kind=Scope.Kind.OFFERING,
        )
        return (
            CourseOffering.objects.filter(pk__in=scopes)
            .select_related("course", "term", "program")
            .order_by("term__year", "term__season", "course__code", "section")
        )

    def instructor_roster(self, offering):
        return scoping.scope_enrollments(
            self.actor, Enrollment.objects.filter(offering=offering).select_related("student")
        ).order_by("student__last_name", "student__first_name", "student__username")

    def student_enrollments(self):
        assignments = RoleAssignment.objects.filter(
            user=self.actor, role_id="student", revoked_at__isnull=True
        ).values_list("scope_id", flat=True)
        if not assignments.exists():
            raise PermissionDenied("Student access is required.")
        return (
            Enrollment.objects.filter(student=self.actor, offering_id__in=assignments)
            .select_related("offering__course", "offering__term", "offering__program")
            .order_by("offering__term__year", "offering__term__season", "offering__course__code")
        )

    def coordinator_programs(self):
        scopes = Scope.objects.filter(
            authorization.scope_filter(self.actor, "program.manage", prefix=""),
            kind=Scope.Kind.PROGRAM,
        )
        if not scopes.exists():
            raise PermissionDenied("Program coordinator access is required.")
        return Program.objects.filter(pk__in=scopes).select_related("department")

    def coordinator_offerings(self, programs):
        return CourseOffering.objects.filter(program__in=programs).select_related("course", "term")

    def coordinator_memberships(self, programs):
        return ProgramMembership.objects.filter(program__in=programs).select_related(
            "user", "program"
        )

    @staticmethod
    def membership_user_data(membership):
        return {
            **user_data(membership.user),
            "program_id": str(membership.program_id),
            "student_number": membership.student_number,
            "membership_status": membership.status,
        }
