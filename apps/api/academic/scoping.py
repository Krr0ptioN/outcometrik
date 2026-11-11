"""Academic queryset visibility derived only from access roles and grants."""

from access.models import RoleAssignment, Scope
from access.policy import authorization
from django.db.models import Q

from .models import Institution, Program


def _scope_ids(user, capability, kind):
    return Scope.objects.filter(
        authorization.scope_filter(user, capability, prefix=""), kind=kind
    ).values_list("pk", flat=True)


def _program_ids(user, capability="program.manage"):
    return _scope_ids(user, capability, Scope.Kind.PROGRAM)


def _offering_ids(user, capability="offering.manage"):
    return _scope_ids(user, capability, Scope.Kind.OFFERING)


def _student_offering_ids(user):
    return RoleAssignment.objects.filter(
        user=user, role_id="student", revoked_at__isnull=True
    ).values_list("scope_id", flat=True)


def scope_programs(user, qs):
    return qs.filter(
        Q(pk__in=_program_ids(user)) | Q(offerings__pk__in=_offering_ids(user))
    ).distinct()


def scope_offerings(user, qs):
    return qs.filter(
        Q(pk__in=_offering_ids(user)) | Q(pk__in=_student_offering_ids(user))
    ).distinct()


def scope_enrollments(user, qs):
    # Students may see only their own roster row. Staff visibility comes from grades.view;
    # student grants are deliberately ownership and release checked by policy selectors.
    staff_scopes = _scope_ids(user, "grades.view", Scope.Kind.OFFERING)
    student_scopes = _student_offering_ids(user)
    return qs.filter(
        Q(offering_id__in=staff_scopes) | Q(student=user, offering_id__in=student_scopes)
    ).distinct()


def scope_memberships(user, qs):
    programs = _program_ids(user)
    return qs.filter(Q(program_id__in=programs) | Q(user=user)).distinct()


def scope_assignments(user, qs):
    offerings = _offering_ids(user)
    return qs.filter(offering_id__in=offerings).distinct()


def scope_institutions(user, qs):
    programs = _program_ids(user)
    institution_ids = set(_scope_ids(user, "program.manage", Scope.Kind.INSTITUTION))
    institution_ids.update(
        Scope.objects.filter(pk__in=programs).values_list("parent_id", flat=True)
    )
    return qs.filter(pk__in=institution_ids).distinct()


def scope_departments(user, qs):
    programs = scope_programs(user, Program.objects)
    admin_institutions = _scope_ids(user, "access.manage", Scope.Kind.INSTITUTION)
    return qs.filter(Q(programs__in=programs) | Q(institution_id__in=admin_institutions)).distinct()


def scope_terms(user, qs):
    offerings = set(_offering_ids(user)) | set(_student_offering_ids(user))
    institutions = scope_institutions(user, Institution.objects)
    return qs.filter(Q(institution__in=institutions) | Q(offerings__pk__in=offerings)).distinct()


def scope_courses(user, qs):
    offerings = set(_offering_ids(user)) | set(_student_offering_ids(user))
    programs = scope_programs(user, Program.objects)
    admin_institutions = _scope_ids(user, "access.manage", Scope.Kind.INSTITUTION)
    return qs.filter(
        Q(offerings__pk__in=offerings)
        | Q(program_courses__program__in=programs)
        | Q(home_department__institution_id__in=admin_institutions)
    ).distinct()
