from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from ..access_control import OfferingAuthorization, require
from ..models import Enrollment, Grade, GradeBatch, GradeHistory
from .base import AcademicService
from .grade_validation import GradeValidator
from .revisions import RevisionTracker

GRADE_EDIT = "grades.edit"


class GradeVersionConflict(Exception):
    def __init__(self, current_version: int):
        super().__init__("The grade was changed by someone else.")
        self.current_version = current_version


class GradeService(AcademicService):
    model = Grade
    immutable_fields = ("enrollment", "assessment", "batch")

    def visible_queryset(self, queryset):
        candidates = Grade.objects.values_list("offering_id", flat=True).distinct()
        staff_offerings = OfferingAuthorization.editable_ids(
            actor=self.actor, candidate_ids=candidates
        )
        return queryset.select_related("assessment", "batch").filter(
            Q(offering_id__in=staff_offerings)
            | Q(enrollment__student=self.actor, batch__released_at__isnull=False)
        )

    def update_access(self, instance):
        return GRADE_EDIT, instance.offering_id

    @transaction.atomic
    def create(self, *, enrollment, assessment, batch, state, points_earned=None, reason=""):
        require(self.actor, GRADE_EDIT, enrollment.offering_id)
        # Serialize writes with release before deciding whether a reason is required.
        batch = GradeBatch.objects.select_for_update().get(pk=batch.pk)
        enrollment = (
            Enrollment.objects.select_for_update(of=("self",))
            .select_related("offering")
            .get(pk=enrollment.pk)
        )
        GradeValidator.validate(
            enrollment=enrollment,
            assessment=assessment,
            batch=batch,
            state=state,
            points_earned=points_earned,
            points_possible=assessment.points_possible,
        )

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
            RevisionTracker.bump(
                program_id=enrollment.offering.program_id, offering_id=enrollment.offering_id
            )
        return grade

    @transaction.atomic
    def correct(self, *, grade, expected_version, state, points_earned=None, reason=""):
        identity = Grade.objects.values("batch_id", "enrollment_id").get(pk=grade.pk)
        # All grade mutations take locks in batch, enrollment, grade order.
        batch = GradeBatch.objects.select_for_update().get(pk=identity["batch_id"])
        enrollment = Enrollment.objects.select_for_update().get(pk=identity["enrollment_id"])
        locked = (
            Grade.objects.select_for_update(of=("self",))
            .select_related("offering", "assessment")
            .get(pk=grade.pk)
        )
        if locked.batch_id != batch.pk or locked.enrollment_id != enrollment.pk:
            raise ValidationError("The grade context changed; retry the operation.")
        require(self.actor, GRADE_EDIT, locked.offering_id)
        if locked.version != expected_version:
            raise GradeVersionConflict(locked.version)
        GradeValidator.validate(
            enrollment=enrollment,
            assessment=locked.assessment,
            batch=batch,
            state=state,
            points_earned=points_earned,
            points_possible=locked.points_possible,
        )

        if state == locked.state and points_earned == locked.points_earned:
            return locked  # no-op: no version bump, no history row

        released = batch.released_at is not None
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
            RevisionTracker.bump(
                program_id=locked.offering.program_id, offering_id=locked.offering_id
            )
        return locked

    def history(self, *, grade):
        require(self.actor, GRADE_EDIT, grade.offering_id)
        return grade.history.select_related("changed_by")


class GradeBatchService(AcademicService):
    model = GradeBatch
    immutable_fields = ("offering",)

    def visible_queryset(self, queryset):
        candidates = GradeBatch.objects.values_list("offering_id", flat=True).distinct()
        return queryset.filter(
            offering_id__in=OfferingAuthorization.editable_ids(
                actor=self.actor, candidate_ids=candidates
            )
        )

    def create_access(self, data):
        return GRADE_EDIT, data["offering"].pk

    def update_access(self, instance):
        return GRADE_EDIT, instance.offering_id

    @transaction.atomic
    def release(self, *, batch):
        batch = (
            GradeBatch.objects.select_for_update(of=("self",))
            .select_related("offering")
            .get(pk=batch.pk)
        )
        require(self.actor, GRADE_EDIT, batch.offering_id)
        if batch.released_at is None:
            batch.released_at = timezone.now()
            batch.released_by = self.actor
            batch.save()
            # Previously private grades become eligible inputs when first released.
            if Grade.objects.filter(batch=batch).exists():
                RevisionTracker.bump(
                    program_id=batch.offering.program_id, offering_id=batch.offering_id
                )
        return batch
