from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from ..access_control import require
from ..models import Assessment, Enrollment, Grade, GradeBatch, GradeHistory
from .base import AcademicService
from .offerings import bump_revisions

GRADE_EDIT = "grades.edit"


class GradeVersionConflict(Exception):
    def __init__(self, current_version: int):
        super().__init__("The grade was changed by someone else.")
        self.current_version = current_version


def _editable_offering_ids(actor, candidate_ids):
    allowed = set()
    for offering_id in candidate_ids:
        try:
            require(actor, GRADE_EDIT, offering_id)
        except PermissionDenied:
            continue
        allowed.add(offering_id)
    return allowed


def _check_value(state, points, points_possible):
    if state == Grade.State.SCORED:
        if points is None:
            raise ValidationError({"points_earned": "Required when the grade is scored."})
        if points < 0 or points > points_possible:
            raise ValidationError({"points_earned": f"Must be between 0 and {points_possible}."})
    elif points is not None:
        raise ValidationError({"points_earned": "Must be empty unless the grade is scored."})


def _check_context(enrollment, assessment, batch):
    if enrollment.status != Enrollment.Status.ENROLLED:
        raise ValidationError("The enrollment is not active.")
    if assessment.offering_id != enrollment.offering_id:
        raise ValidationError({"assessment": "This assessment is not part of the offering."})
    if assessment.status != Assessment.Status.APPROVED:
        raise ValidationError({"assessment": "This assessment is not approved."})
    if batch.offering_id != enrollment.offering_id:
        raise ValidationError({"batch": "This batch belongs to a different offering."})


class GradeService(AcademicService):
    model = Grade
    immutable_fields = ("enrollment", "assessment", "batch")

    def visible_queryset(self, queryset):
        candidates = Grade.objects.values_list("offering_id", flat=True).distinct()
        staff_offerings = _editable_offering_ids(self.actor, candidates)
        return queryset.filter(
            Q(offering_id__in=staff_offerings)
            | Q(enrollment__student=self.actor, batch__released_at__isnull=False)
        )

    def update_access(self, instance):
        return GRADE_EDIT, instance.offering_id

    @transaction.atomic
    def create(self, *, enrollment, assessment, batch, state, points_earned=None, reason=""):
        require(self.actor, GRADE_EDIT, enrollment.offering_id)
        enrollment = (
            Enrollment.objects.select_for_update().select_related("offering").get(pk=enrollment.pk)
        )
        batch = GradeBatch.objects.get(pk=batch.pk)
        _check_context(enrollment, assessment, batch)
        _check_value(state, points_earned, assessment.points_possible)

        released = batch.released_at is not None
        if released and not reason.strip():
            raise ValidationError({"reason": "A reason is required after release."})
        if Grade.objects.filter(enrollment=enrollment, assessment=assessment).exists():
            raise ValidationError(
                "A grade already exists for this student and assessment. Update it instead."
            )

        grade = Grade(
            offering=enrollment.offering,
            enrollment=enrollment,
            assessment=assessment,
            batch=batch,
            state=state,
            points_earned=points_earned,
            points_possible=assessment.points_possible,
            version=1,
        )
        try:
            grade.save()
        except IntegrityError as exc:
            raise ValidationError(
                "A grade already exists for this student and assessment."
            ) from exc
        GradeHistory.objects.create(
            grade=grade,
            version=1,
            old_state="",
            old_points_earned=None,
            new_state=state,
            new_points_earned=points_earned,
            reason=reason or "created",
            changed_by=self.actor,
        )
        if released:
            bump_revisions(
                program_id=enrollment.offering.program_id, offering_id=enrollment.offering_id
            )
        return grade

    @transaction.atomic
    def correct(self, *, grade, expected_version, state, points_earned=None, reason=""):
        locked = (
            Grade.objects.select_for_update()
            .select_related("offering", "enrollment", "assessment", "batch")
            .get(pk=grade.pk)
        )
        require(self.actor, GRADE_EDIT, locked.offering_id)
        if locked.version != expected_version:
            raise GradeVersionConflict(locked.version)
        _check_context(locked.enrollment, locked.assessment, locked.batch)
        _check_value(state, points_earned, locked.points_possible)

        if state == locked.state and points_earned == locked.points_earned:
            return locked  # no-op: no version bump, no history row

        released = locked.batch.released_at is not None
        if released and not reason.strip():
            raise ValidationError({"reason": "A reason is required after release."})

        old_state, old_points = locked.state, locked.points_earned
        locked.state = state
        locked.points_earned = points_earned
        locked.version += 1
        locked.save()
        GradeHistory.objects.create(
            grade=locked,
            version=locked.version,
            old_state=old_state,
            old_points_earned=old_points,
            new_state=state,
            new_points_earned=points_earned,
            reason=reason,
            changed_by=self.actor,
        )
        if released:
            bump_revisions(program_id=locked.offering.program_id, offering_id=locked.offering_id)
        return locked

    def history(self, *, grade):
        require(self.actor, GRADE_EDIT, grade.offering_id)
        return grade.history.select_related("changed_by")


class GradeBatchService(AcademicService):
    model = GradeBatch
    immutable_fields = ("offering",)

    def visible_queryset(self, queryset):
        candidates = GradeBatch.objects.values_list("offering_id", flat=True).distinct()
        return queryset.filter(offering_id__in=_editable_offering_ids(self.actor, candidates))

    def create_access(self, data):
        return GRADE_EDIT, data["offering"].pk

    def update_access(self, instance):
        return GRADE_EDIT, instance.offering_id

    @transaction.atomic
    def release(self, *, batch):
        batch = GradeBatch.objects.select_for_update().get(pk=batch.pk)
        require(self.actor, GRADE_EDIT, batch.offering_id)
        if batch.released_at is None:
            batch.released_at = timezone.now()
            batch.released_by = self.actor
            batch.save()
        return batch
