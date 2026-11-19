from typing import Any

from access.policy import AuthorizationService
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from wireup import injectable

from ..access_control import OfferingAuthorization
from ..models import CourseOffering, Enrollment, Grade, GradeBatch, GradeHistory
from .grade_validation import GradeValidator
from .revisions import RevisionTracker


class GradeVersionConflict(Exception):
    def __init__(
        self,
        current_version: int | None = None,
        *,
        current_input_revision: int | None = None,
        detail: str = "The grade was changed by someone else.",
    ):
        super().__init__(detail)
        self.current_version = current_version
        self.current_input_revision = current_input_revision
        self.detail = detail


@injectable
class GradeService:
    """Manages student grades and history with explicit dependency injection and actor scoping."""

    model = Grade
    immutable_fields = ("enrollment", "assessment", "batch")

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Grade.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Grade.objects.all()
        effective_actor = actor if actor is not None else self.actor
        if effective_actor is None or not getattr(effective_actor, "is_authenticated", False):
            return queryset.none()
        candidates = Grade.objects.values_list("offering_id", flat=True).distinct()
        staff_offerings = OfferingAuthorization.editable_ids(
            actor=effective_actor, candidate_ids=candidates
        )
        return queryset.select_related("assessment", "batch").filter(
            Q(offering_id__in=staff_offerings)
            | Q(enrollment__student=effective_actor, batch__released_at__isnull=False)
        )

    @transaction.atomic
    def create(
        self,
        *,
        enrollment,
        assessment,
        batch,
        state,
        points_earned=None,
        reason="",
        actor: Any = None,
    ) -> Grade:
        effective_actor = actor if actor is not None else self.actor
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
            changed_by=effective_actor,
        )
        if released:
            RevisionTracker.bump(
                program_id=enrollment.offering.program_id, offering_id=enrollment.offering_id
            )
        return grade

    @transaction.atomic
    def correct(
        self,
        *,
        grade,
        expected_version,
        state,
        points_earned=None,
        reason="",
        actor: Any = None,
    ) -> Grade:
        effective_actor = actor if actor is not None else self.actor
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
            changed_by=effective_actor,
        )
        if released:
            RevisionTracker.bump(
                program_id=locked.offering.program_id, offering_id=locked.offering_id
            )
        return locked

    @transaction.atomic
    def bulk_save(
        self,
        *,
        offering: CourseOffering,
        items: list[dict],
        idempotency_key: str,
        expected_input_revision: int | None = None,
        actor: Any = None,
    ) -> dict[str, Any]:
        effective_actor = actor if actor is not None else self.actor
        locked_offering = (
            CourseOffering.objects.select_for_update().select_related("program").get(pk=offering.pk)
        )

        # Collect all referenced batches, enrollments, and existing grades to lock in canonical order.
        enrollment_ids = {item["enrollment"].pk for item in items}
        assessment_ids = {item["assessment"].pk for item in items}
        existing_rows = list(
            Grade.objects.filter(
                offering_id=locked_offering.pk,
                enrollment_id__in=enrollment_ids,
                assessment_id__in=assessment_ids,
            ).values("pk", "batch_id", "enrollment_id", "assessment_id")
        )
        batch_ids = {item["batch"].pk for item in items} | {
            row["batch_id"] for row in existing_rows
        }

        locked_batches = {
            b.pk: b
            for b in GradeBatch.objects.select_for_update().filter(pk__in=batch_ids).order_by("pk")
        }
        locked_enrollments = {
            e.pk: e
            for e in Enrollment.objects.select_for_update(of=("self",))
            .select_related("offering")
            .filter(pk__in=enrollment_ids)
            .order_by("pk")
        }
        locked_grades = {
            (g.enrollment_id, g.assessment_id): g
            for g in Grade.objects.select_for_update(of=("self",))
            .select_related("offering", "assessment", "batch")
            .filter(pk__in=[row["pk"] for row in existing_rows])
            .order_by("pk")
        }

        GradeValidator.validate_bulk_items(
            offering=locked_offering,
            items=items,
            locked_batches=locked_batches,
            locked_enrollments=locked_enrollments,
            existing_grades=locked_grades,
        )

        all_match = all(
            (existing := locked_grades.get((item["enrollment"].pk, item["assessment"].pk)))
            is not None
            and existing.state == item["state"]
            and existing.points_earned == item.get("points_earned")
            for item in items
        )

        if not all_match:
            if (
                expected_input_revision is not None
                and locked_offering.input_revision != expected_input_revision
            ):
                raise GradeVersionConflict(
                    current_input_revision=locked_offering.input_revision,
                    detail="The gradebook was updated by someone else. Refresh the latest grades and retry.",
                )

            for item in items:
                pair = (item["enrollment"].pk, item["assessment"].pk)
                existing = locked_grades.get(pair)
                expected_version = item.get("expected_version")
                state = item["state"]
                points_earned = item.get("points_earned")
                item_matches = (
                    existing is not None
                    and existing.state == state
                    and existing.points_earned == points_earned
                )
                if existing is not None:
                    if (
                        expected_version is not None
                        and existing.version != expected_version
                        and not item_matches
                    ):
                        raise GradeVersionConflict(
                            existing.version,
                            current_input_revision=locked_offering.input_revision,
                            detail="A grade was changed by someone else. Refresh the latest grades and retry.",
                        )
                elif expected_version is not None:
                    raise GradeVersionConflict(
                        0,
                        current_input_revision=locked_offering.input_revision,
                        detail="A grade version expectation did not match the current gradebook state.",
                    )

        saved_grades: list[Grade] = []
        any_released_change = False

        for item in items:
            enrollment = locked_enrollments[item["enrollment"].pk]
            assessment = item["assessment"]
            batch = locked_batches[item["batch"].pk]
            state = item["state"]
            points_earned = item.get("points_earned")
            reason = (item.get("reason") or "").strip()
            existing = locked_grades.get((enrollment.pk, assessment.pk))

            if existing is None:
                grade = Grade(
                    offering=locked_offering,
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
                    changed_by=effective_actor,
                )
                if batch.released_at is not None:
                    any_released_change = True
                saved_grades.append(grade)
            else:
                if existing.state == state and existing.points_earned == points_earned:
                    saved_grades.append(existing)
                    continue

                effective_batch = locked_batches[existing.batch_id]
                old_state, old_points = existing.state, existing.points_earned
                existing.state = state
                existing.points_earned = points_earned
                existing.version += 1
                existing.save()
                GradeHistory.objects.create(
                    grade=existing,
                    version=existing.version,
                    old_state=old_state,
                    old_points_earned=old_points,
                    new_state=state,
                    new_points_earned=points_earned,
                    reason=reason,
                    changed_by=effective_actor,
                )
                if effective_batch.released_at is not None:
                    any_released_change = True
                saved_grades.append(existing)

        if any_released_change:
            RevisionTracker.bump(
                program_id=locked_offering.program_id, offering_id=locked_offering.pk
            )
            locked_offering.refresh_from_db(fields=["input_revision"])

        return {
            "offering": str(locked_offering.pk),
            "input_revision": locked_offering.input_revision,
            "idempotency_key": idempotency_key,
            "grades": saved_grades,
        }

    def history(self, *, grade):
        return grade.history.select_related("changed_by")


@injectable
class GradeBatchService:
    """Manages grade batches with explicit dependency injection and actor scoping."""

    model = GradeBatch
    immutable_fields = ("offering",)

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(GradeBatch.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = GradeBatch.objects.all()
        effective_actor = actor if actor is not None else self.actor
        if effective_actor is None or not getattr(effective_actor, "is_authenticated", False):
            return queryset.none()
        candidates = GradeBatch.objects.values_list("offering_id", flat=True).distinct()
        return queryset.filter(
            offering_id__in=OfferingAuthorization.editable_ids(
                actor=effective_actor, candidate_ids=candidates
            )
        )

    @transaction.atomic
    def create(self, **data) -> GradeBatch:
        try:
            return GradeBatch.objects.create(**data)
        except IntegrityError as exc:
            raise ValidationError("This grade batch conflicts with an existing record.") from exc

    @transaction.atomic
    def update(self, *, instance: GradeBatch, **data) -> GradeBatch:
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            raise ValidationError("This grade batch conflicts with an existing record.") from exc
        return instance

    @transaction.atomic
    def release(self, *, batch, actor: Any = None) -> GradeBatch:
        effective_actor = actor if actor is not None else self.actor
        batch = (
            GradeBatch.objects.select_for_update(of=("self",))
            .select_related("offering")
            .get(pk=batch.pk)
        )
        if batch.released_at is None:
            batch.released_at = timezone.now()
            batch.released_by = effective_actor
            batch.save()
            # Previously private grades become eligible inputs when first released.
            if Grade.objects.filter(batch=batch).exists():
                RevisionTracker.bump(
                    program_id=batch.offering.program_id, offering_id=batch.offering_id
                )
        return batch
