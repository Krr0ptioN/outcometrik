from typing import Any

from access.identity import user_data
from access.models import DirectCapabilityGrant, RoleAssignment, Scope
from access.policy import AuthorizationService
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from wireup import injectable

from .. import scoping
from ..models import CourseOffering, Enrollment, Program, ProgramMembership


@injectable
class WorkspaceService:
    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def instructor_offerings(self, actor: Any = None):
        effective_actor = actor if actor is not None else self.actor
        assignments = RoleAssignment.objects.filter(
            user=effective_actor, role_id="instructor", revoked_at__isnull=True
        )
        if not assignments.exists():
            raise PermissionDenied("Instructor access is required.")
        grant_scopes = DirectCapabilityGrant.objects.filter(
            user=effective_actor, capability_id="grades.view", revoked_at__isnull=True
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

    def instructor_roster(self, offering, actor: Any = None):
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_enrollments(
            effective_actor, Enrollment.objects.filter(offering=offering).select_related("student")
        ).order_by("student__last_name", "student__first_name", "student__username")

    def student_enrollments(self, actor: Any = None):
        effective_actor = actor if actor is not None else self.actor
        assignments = RoleAssignment.objects.filter(
            user=effective_actor, role_id="student", revoked_at__isnull=True
        ).values_list("scope_id", flat=True)
        if not assignments.exists():
            raise PermissionDenied("Student access is required.")
        return (
            Enrollment.objects.filter(student=effective_actor, offering_id__in=assignments)
            .select_related("offering__course", "offering__term", "offering__program")
            .order_by("offering__term__year", "offering__term__season", "offering__course__code")
        )

    def coordinator_programs(self, actor: Any = None):
        effective_actor = actor if actor is not None else self.actor
        scopes = Scope.objects.filter(
            self.auth_service.scope_filter(effective_actor, "program.manage", prefix=""),
            kind=Scope.Kind.PROGRAM,
        )
        if not scopes.exists():
            raise PermissionDenied("Program coordinator access is required.")
        return Program.objects.filter(pk__in=scopes).select_related("department")

    def coordinator_offerings(self, programs, actor: Any = None):
        return CourseOffering.objects.filter(program__in=programs).select_related("course", "term")

    def coordinator_memberships(self, programs, actor: Any = None):
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
