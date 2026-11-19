"""Grade invariants shared by grade entry and correction."""

from django.core.exceptions import ValidationError

from ..models import Assessment, Enrollment, Grade


class GradeValidator:
    @staticmethod
    def validate(*, enrollment, assessment, batch, state, points_earned, points_possible):
        if enrollment.status != Enrollment.Status.ENROLLED:
            raise ValidationError("The enrollment is not active.")

        if assessment.offering_id != enrollment.offering_id:
            raise ValidationError({"assessment": "This assessment is not part of the offering."})
        if assessment.status != Assessment.Status.APPROVED:
            raise ValidationError({"assessment": "This assessment is not approved."})

        if batch.offering_id != enrollment.offering_id:
            raise ValidationError({"batch": "This batch belongs to a different offering."})

        if state == Grade.State.SCORED:
            if points_earned is None:
                raise ValidationError({"points_earned": "Required when the grade is scored."})
            if points_earned < 0 or points_earned > points_possible:
                raise ValidationError(
                    {"points_earned": f"Must be between 0 and {points_possible}."}
                )

        elif points_earned is not None:
            raise ValidationError({"points_earned": "Must be empty unless the grade is scored."})

    @staticmethod
    def validate_bulk_items(
        *,
        offering,
        items: list[dict],
        locked_batches: dict,
        locked_enrollments: dict,
        existing_grades: dict,
    ) -> None:
        if not items:
            raise ValidationError({"items": "At least one grade item is required."})

        seen_pairs: set[tuple[str, str]] = set()
        for idx, item in enumerate(items):
            raw_enrollment = item["enrollment"]
            raw_assessment = item["assessment"]
            raw_batch = item["batch"]
            state = item["state"]
            points_earned = item.get("points_earned")
            reason = (item.get("reason") or "").strip()

            enrollment = locked_enrollments.get(raw_enrollment.pk, raw_enrollment)
            batch = locked_batches.get(raw_batch.pk, raw_batch)
            assessment = raw_assessment

            if enrollment.offering_id != offering.pk:
                raise ValidationError(
                    {"items": f"Item {idx}: enrollment does not belong to the target offering."}
                )
            if assessment.offering_id != offering.pk:
                raise ValidationError(
                    {"items": f"Item {idx}: assessment does not belong to the target offering."}
                )
            if batch.offering_id != offering.pk:
                raise ValidationError(
                    {"items": f"Item {idx}: batch does not belong to the target offering."}
                )

            pair = (str(enrollment.pk), str(assessment.pk))
            if pair in seen_pairs:
                raise ValidationError(
                    {"items": f"Item {idx}: duplicate grade entry for student and assessment."}
                )
            seen_pairs.add(pair)

            existing = existing_grades.get((enrollment.pk, assessment.pk))
            effective_batch = (
                locked_batches.get(existing.batch_id, batch) if existing is not None else batch
            )
            points_possible = (
                existing.points_possible if existing is not None else assessment.points_possible
            )

            try:
                GradeValidator.validate(
                    enrollment=enrollment,
                    assessment=assessment,
                    batch=effective_batch,
                    state=state,
                    points_earned=points_earned,
                    points_possible=points_possible,
                )
            except ValidationError as exc:
                details = getattr(exc, "message_dict", None)
                if details:
                    summary = "; ".join(
                        f"{field}: {', '.join(msgs)}" for field, msgs in details.items()
                    )
                else:
                    summary = "; ".join(exc.messages)
                raise ValidationError({"items": f"Item {idx}: {summary}"}) from exc

            is_noop = (
                existing is not None
                and existing.state == state
                and existing.points_earned == points_earned
            )
            released = effective_batch.released_at is not None
            if released and not is_noop and not reason:
                raise ValidationError(
                    {"items": f"Item {idx}: reason: A reason is required after release."}
                )
