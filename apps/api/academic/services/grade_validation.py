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
