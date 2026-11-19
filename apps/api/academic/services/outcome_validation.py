"""Domain validation for ProgramOutcomeSet and ProgramOutcome invariants."""

from django.core.exceptions import ValidationError

from ..models import ProgramOutcomeSet

OUTCOME_TEXT_FIELDS = ("code", "label", "description", "source_url")


class ProgramOutcomeSetValidator:
    """Domain validator for ProgramOutcomeSet lifecycle and ProgramOutcome integrity."""

    @staticmethod
    def validate_activation(outcome_set, effective_date):
        """Validate prerequisites before activating a program outcome set."""
        if outcome_set.status != ProgramOutcomeSet.Status.DRAFT:
            raise ValidationError({"status": "Only a draft set can be activated."})
        if effective_date is None:
            raise ValidationError({"effective_date": "Required for activation."})
        if not outcome_set.source_reference.strip():
            raise ValidationError({"source_reference": "Required for activation."})

        outcomes = list(outcome_set.outcomes.order_by("ordering"))
        if not outcomes:
            raise ValidationError({"outcomes": "A set needs at least one outcome."})
        for outcome in outcomes:
            for field in OUTCOME_TEXT_FIELDS:
                if not str(getattr(outcome, field)).strip():
                    raise ValidationError(
                        {"outcomes": f"{outcome.code or '?'}: {field} is required."}
                    )
        if [o.ordering for o in outcomes] != list(range(1, len(outcomes) + 1)):
            raise ValidationError({"outcomes": "Ordering must be 1..N with no gaps."})

        latest = (
            ProgramOutcomeSet.objects.filter(
                program_id=outcome_set.program_id,
                status=ProgramOutcomeSet.Status.ACTIVE,
            )
            .exclude(pk=outcome_set.pk)
            .order_by("-effective_date")
            .first()
        )
        if latest and effective_date <= latest.effective_date:
            raise ValidationError(
                {"effective_date": "Must be later than the current active set's effective date."}
            )

    @staticmethod
    def validate_mutation(outcome_set, data=None, exclude_pk=None):
        """Ensure child outcomes can only be created/updated when the parent set is in draft status,
        and ensure code and ordering uniqueness among siblings.
        """
        if outcome_set.status != ProgramOutcomeSet.Status.DRAFT:
            raise ValidationError("Outcomes of an active set are immutable. Create a new version.")
        if data:
            siblings = outcome_set.outcomes.exclude(pk=exclude_pk)
            for field in ("code", "ordering"):
                if field in data and siblings.filter(**{field: data[field]}).exists():
                    raise ValidationError({field: "Must be unique within the set."})

    @staticmethod
    def validate_set_update(instance, data=None):
        """Ensure an active outcome set cannot be edited."""
        if instance.status == ProgramOutcomeSet.Status.ACTIVE:
            raise ValidationError("An active set is immutable. Create a new version.")
