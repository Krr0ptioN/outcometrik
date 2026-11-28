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


OFFERING_READ_CAPABILITIES = (
    "offering.manage",
    "grades.view",
    "grades.edit",
    "grades.release",
    "syllabus.draft",
)

ENROLLMENT_STAFF_CAPABILITIES = (
    "grades.view",
    "grades.edit",
    "grades.release",
    "offering.manage",
)


def scope_offerings(user, qs):
    staff_scopes = set()
    for capability in OFFERING_READ_CAPABILITIES:
        staff_scopes.update(_offering_ids(user, capability))
    return qs.filter(Q(pk__in=staff_scopes) | Q(pk__in=_student_offering_ids(user))).distinct()


def scope_syllabi(user, qs):
    # Staff draft/manage visibility derives from offering-scoped capabilities;
    # enrolled students see only the official (approved) syllabus of their offering.
    # `scope_filter` excludes student role assignments, so student scopes are collected
    # directly and the status restriction applies to those scopes only.
    from .models import Syllabus

    approved = Syllabus.Status.APPROVED
    staff_scopes = set(_scope_ids(user, "syllabus.draft", Scope.Kind.OFFERING))
    student_scopes = set(_student_offering_ids(user))
    if not student_scopes:
        return qs.filter(offering_id__in=staff_scopes).distinct()
    if not staff_scopes:
        return qs.filter(offering_id__in=student_scopes, status=approved).distinct()
    return qs.filter(
        Q(offering_id__in=staff_scopes) | Q(offering_id__in=student_scopes, status=approved)
    ).distinct()


def scope_enrollments(user, qs):
    # Students may see only their own roster row. Staff visibility comes from offering-level
    # grade/management capabilities; student grants are deliberately ownership and release
    # checked by policy selectors.
    staff_scopes = set()
    for capability in ENROLLMENT_STAFF_CAPABILITIES:
        staff_scopes.update(_offering_ids(user, capability))
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


CALCULATION_PROGRAM_CAPABILITIES = (
    "outcomes.view",
    "program.manage",
)

CALCULATION_OFFERING_CAPABILITIES = (
    "grades.view",
    "grades.edit",
    "grades.release",
    "offering.manage",
    "outcomes.view",
)


def scope_calculation_runs(user, qs):
    """Calculation runs are visible only to authorized staff; never exposed to students."""
    from .models import CalculationRun

    if user is None or not getattr(user, "is_authenticated", False):
        return qs.none()

    program_ids = set()
    for capability in CALCULATION_PROGRAM_CAPABILITIES:
        program_ids.update(_program_ids(user, capability))

    offering_ids = set()
    for capability in CALCULATION_OFFERING_CAPABILITIES:
        offering_ids.update(_offering_ids(user, capability))

    if not program_ids and not offering_ids:
        return qs.none()

    return qs.filter(
        Q(program_id__in=program_ids)
        | Q(scope_kind=CalculationRun.ScopeKind.OFFERING, offering_id__in=offering_ids)
    ).distinct()


PUBLICATION_PROGRAM_CAPABILITIES = (
    "outcomes.view",
    "outcomes.publish",
    "program.manage",
)

PUBLICATION_OFFERING_CAPABILITIES = (
    "grades.view",
    "grades.edit",
    "grades.release",
    "offering.manage",
    "outcomes.view",
)


def _staff_publication_scope_ids(user) -> tuple[set, set]:
    program_ids = set()
    for capability in PUBLICATION_PROGRAM_CAPABILITIES:
        program_ids.update(_program_ids(user, capability))

    offering_ids = set()
    for capability in PUBLICATION_OFFERING_CAPABILITIES:
        offering_ids.update(_offering_ids(user, capability))

    return program_ids, offering_ids


def has_staff_publication_access(user, publication) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    program_ids, offering_ids = _staff_publication_scope_ids(user)
    if publication.program_id in program_ids:
        return True
    return publication.offering_id is not None and publication.offering_id in offering_ids


def scope_publications(user, qs):
    """Coordinators/admins/staff see scoped publications; students see only their student-audience publications."""
    from .models import Publication

    if user is None or not getattr(user, "is_authenticated", False):
        return qs.none()

    program_ids, offering_ids = _staff_publication_scope_ids(user)
    student_offering_ids = set(_student_offering_ids(user))

    clauses = Q()
    has_clause = False

    if program_ids:
        clauses |= Q(program_id__in=program_ids)
        has_clause = True
    if offering_ids:
        clauses |= Q(offering_id__in=offering_ids)
        has_clause = True
    if student_offering_ids:
        from django.db.models import Exists, OuterRef

        from .models import OutcomeScore

        student_program_ids = set(
            Scope.objects.filter(pk__in=student_offering_ids).values_list("parent_id", flat=True)
        )
        has_own_score = Exists(OutcomeScore.objects.filter(run_id=OuterRef("run_id"), student=user))
        student_clause = (
            Q(
                audience=Publication.Audience.STUDENT,
                offering_id__in=student_offering_ids,
            )
            & has_own_score
        )
        if student_program_ids:
            student_clause |= (
                Q(
                    audience=Publication.Audience.STUDENT,
                    offering__isnull=True,
                    program_id__in=student_program_ids,
                )
                & has_own_score
            )
        clauses |= student_clause
        has_clause = True

    if not has_clause:
        return qs.none()

    return qs.filter(clauses)
