"""Domain validation for Syllabus and syllabus child component invariants."""

from django.core.exceptions import ValidationError

from ..models import Syllabus


class SyllabusValidator:
    """Domain validator for syllabus lifecycle and draft-time editing invariants."""

    @staticmethod
    def validate_editable(syllabus):
        """Ensure syllabus is a draft version; locked/approved versions cannot be modified."""
        if syllabus.status != Syllabus.Status.DRAFT:
            raise ValidationError("This syllabus version is locked; create a revision instead.")
        return syllabus

    @staticmethod
    def validate_creation(offering):
        """Ensure an offering does not have an existing draft or approved syllabus."""
        blocked = offering.syllabi.filter(
            status__in=(Syllabus.Status.DRAFT, Syllabus.Status.APPROVED)
        ).exists()
        if blocked:
            raise ValidationError(
                "A draft or approved syllabus already exists for this offering;"
                " revise the approved version or retire the draft first."
            )

    @staticmethod
    def validate_approval(syllabus, active_set):
        """Ensure syllabus draft fulfills all prerequisite criteria for official approval."""
        SyllabusValidator.validate_editable(syllabus)
        if not syllabus.learning_outcomes.exists() or not syllabus.assessments.exists():
            raise ValidationError("A syllabus version needs at least one LO and one assessment.")
        if not active_set or syllabus.po_set_version != active_set.version:
            raise ValidationError("Syllabus must bind to the program's active PO-set version.")

    @staticmethod
    def validate_revision(syllabus, offering):
        """Ensure only approved syllabi can be revised and no concurrent draft revision exists."""
        if syllabus.status != Syllabus.Status.APPROVED:
            raise ValidationError("Only an approved syllabus version can be revised.")
        if offering.syllabi.filter(status=Syllabus.Status.DRAFT).exists():
            raise ValidationError("A draft revision already exists for this offering.")

    @staticmethod
    def validate_active_po_set_binding(syllabus, active_set):
        """Ensure active PO set exists when binding to syllabus."""
        SyllabusValidator.validate_editable(syllabus)
        if not active_set:
            raise ValidationError("No active PO-set exists for this program.")

    @staticmethod
    def validate_draft_removal(syllabus):
        """Ensure only an empty draft holding no configuration can be retired."""
        SyllabusValidator.validate_editable(syllabus)
        if syllabus.learning_outcomes.exists() or syllabus.assessments.exists():
            raise ValidationError(
                "This syllabus version holds configuration; revise instead of removing it."
            )

    @staticmethod
    def validate_assessment_points(max_points):
        """Ensure assessment max_points is strictly positive."""
        if max_points is not None and max_points <= 0:
            raise ValidationError({"max_points": "Maximum points must be greater than zero."})
