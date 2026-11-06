"""PLACEHOLDER scope rules until AUTH-01 (scoped roles) lands.

Staff see everything. Other users see only what they teach or attend. AUTH-01 should replace
the functions in this file and CanManageAcademicStructure in permissions.py; nothing else
in this app should need to change.
"""

from django.db.models import Q


def _is_admin(user) -> bool:
    return bool(user.is_staff or user.is_superuser)


def scope_programs(user, qs):
    if _is_admin(user):
        return qs
    return qs.filter(
        Q(memberships__user=user) | Q(offerings__instructor_assignments__user=user)
    ).distinct()


def scope_offerings(user, qs):
    if _is_admin(user):
        return qs
    return qs.filter(Q(instructor_assignments__user=user) | Q(enrollments__student=user)).distinct()


def scope_enrollments(user, qs):
    if _is_admin(user):
        return qs
    return qs.filter(Q(student=user) | Q(offering__instructor_assignments__user=user)).distinct()


def scope_memberships(user, qs):
    if _is_admin(user):
        return qs
    return qs.filter(user=user)


def scope_assignments(user, qs):
    if _is_admin(user):
        return qs
    return qs.filter(Q(user=user) | Q(offering__instructor_assignments__user=user)).distinct()
