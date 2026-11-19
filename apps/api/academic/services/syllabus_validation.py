"""Domain validation for Syllabus and syllabus child component invariants."""

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError

<<<<<<< HEAD
from .. import policy
from ..models import Syllabus
=======
from ..models import LearningOutcome, ProgramOutcome, Syllabus, SyllabusAssessment


class SyllabusMappingVersionConflict(Exception):
    """Raised when an atomic matrix replacement uses a stale mapping_revision."""

    def __init__(self, current_revision: int):
        super().__init__("The syllabus mapping matrix was modified by another user.")
        self.current_revision = current_revision
>>>>>>> origin/main


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
        if syllabus.assessment_lo_mappings.exists() or syllabus.lo_po_mappings.exists():
            report = SyllabusValidator.validate_mappings(syllabus=syllabus, bound_po_set=active_set)
            if not report["is_valid_for_approval"]:
                raise ValidationError("; ".join(report["errors"]))

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
        if (
            syllabus.learning_outcomes.exists()
            or syllabus.assessments.exists()
<<<<<<< HEAD
            or syllabus.po_contributions.exists()
=======
            or syllabus.assessment_lo_mappings.exists()
            or syllabus.lo_po_mappings.exists()
>>>>>>> origin/main
        ):
            raise ValidationError(
                "This syllabus version holds configuration; revise instead of removing it."
            )

    @staticmethod
    def validate_assessment_points(max_points):
        """Ensure assessment max_points is strictly positive."""
        if max_points is not None and max_points <= 0:
            raise ValidationError({"max_points": "Maximum points must be greater than zero."})

    @staticmethod
<<<<<<< HEAD
    def validate_po_contribution(syllabus, program_outcome, weight):
        """Ensure course-to-PO contribution weight is integer 1..5 and bound to program's PO set."""
        SyllabusValidator.validate_editable(syllabus)
        if not policy.is_valid_course_po_weight(weight):
            raise ValidationError(
                {
                    "weight": (
                        f"Course-to-PO contribution weight must be an integer between "
                        f"{policy.MIN_COURSE_PO_WEIGHT} and {policy.MAX_COURSE_PO_WEIGHT}."
                    )
                }
            )
        if program_outcome is None:
            raise ValidationError({"program_outcome": "A valid program outcome is required."})
        outcome_set = program_outcome.outcome_set
        if outcome_set.program_id != syllabus.offering.program_id:
            raise ValidationError(
                {
                    "program_outcome": (
                        "Program outcome must belong to the offering's program outcome set."
                    )
                }
            )
        if syllabus.po_set_version is None or outcome_set.version != syllabus.po_set_version:
            raise ValidationError(
                {
                    "program_outcome": (
                        "Program outcome version does not match the syllabus bound PO-set version."
                    )
                }
            )
=======
    def validate_assessment_lo_payload(*, syllabus, mappings: list[dict]) -> list[dict]:
        """Validate A->LO matrix replacement items against syllabus ownership and weight rules."""
        if not isinstance(mappings, list):
            raise ValidationError({"mappings": "Mappings must be a list of mapping entries."})

        seen_pairs: set[tuple[str, str]] = set()
        normalized: list[dict] = []

        for idx, item in enumerate(mappings):
            if not isinstance(item, dict):
                raise ValidationError(
                    {"mappings": f"Entry at index {idx} must be a mapping object."}
                )
            assessment = item.get("assessment")
            if not isinstance(assessment, SyllabusAssessment):
                assessment = SyllabusAssessment.objects.filter(pk=assessment).first()
            if assessment is None:
                raise ValidationError({"mappings": f"Assessment at index {idx} does not exist."})
            if assessment.syllabus_id != syllabus.pk:
                raise ValidationError(
                    {
                        "mappings": (
                            f"Assessment '{assessment.code}' does not belong to this syllabus version."
                        )
                    }
                )

            learning_outcome = item.get("learning_outcome")
            if not isinstance(learning_outcome, LearningOutcome):
                learning_outcome = LearningOutcome.objects.filter(pk=learning_outcome).first()
            if learning_outcome is None:
                raise ValidationError(
                    {"mappings": f"Learning outcome at index {idx} does not exist."}
                )
            if learning_outcome.syllabus_id != syllabus.pk:
                raise ValidationError(
                    {
                        "mappings": (
                            f"Learning outcome '{learning_outcome.code}' does not belong"
                            " to this syllabus version."
                        )
                    }
                )

            pair = (str(assessment.pk), str(learning_outcome.pk))
            if pair in seen_pairs:
                raise ValidationError(
                    {
                        "mappings": (
                            f"Duplicate mapping for assessment '{assessment.code}'"
                            f" and learning outcome '{learning_outcome.code}'."
                        )
                    }
                )
            seen_pairs.add(pair)

            raw_weight = item.get("weight")
            if isinstance(raw_weight, bool) or raw_weight is None:
                raise ValidationError(
                    {"mappings": f"Weight at index {idx} must be a nonnegative decimal."}
                )
            try:
                weight = Decimal(str(raw_weight))
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise ValidationError(
                    {"mappings": f"Weight at index {idx} must be a valid decimal number."}
                ) from exc

            if weight < 0:
                raise ValidationError(
                    {
                        "mappings": (
                            f"Assessment-to-LO weight for '{assessment.code}' ->"
                            f" '{learning_outcome.code}' must be nonnegative."
                        )
                    }
                )

            requested_active = bool(item.get("is_active", True))
            is_active = bool(requested_active and weight > 0)
            normalized.append(
                {
                    "assessment": assessment,
                    "learning_outcome": learning_outcome,
                    "weight": weight,
                    "is_active": is_active,
                }
            )
        return normalized

    @staticmethod
    def validate_lo_po_payload(*, syllabus, mappings: list[dict]) -> list[dict]:
        """Validate LO->PO matrix replacement items against syllabus and bound PO-set scope."""
        if not isinstance(mappings, list):
            raise ValidationError({"mappings": "Mappings must be a list of mapping entries."})
        if syllabus.po_set_version is None:
            raise ValidationError(
                "Syllabus must bind to an active PO-set version before configuring LO-to-PO mappings."
            )

        seen_pairs: set[tuple[str, str]] = set()
        normalized: list[dict] = []

        for idx, item in enumerate(mappings):
            if not isinstance(item, dict):
                raise ValidationError(
                    {"mappings": f"Entry at index {idx} must be a mapping object."}
                )
            learning_outcome = item.get("learning_outcome")
            if not isinstance(learning_outcome, LearningOutcome):
                learning_outcome = LearningOutcome.objects.filter(pk=learning_outcome).first()
            if learning_outcome is None:
                raise ValidationError(
                    {"mappings": f"Learning outcome at index {idx} does not exist."}
                )
            if learning_outcome.syllabus_id != syllabus.pk:
                raise ValidationError(
                    {
                        "mappings": (
                            f"Learning outcome '{learning_outcome.code}' does not belong"
                            " to this syllabus version."
                        )
                    }
                )

            program_outcome = item.get("program_outcome")
            if not isinstance(program_outcome, ProgramOutcome):
                program_outcome = (
                    ProgramOutcome.objects.select_related("outcome_set")
                    .filter(pk=program_outcome)
                    .first()
                )
            if program_outcome is None:
                raise ValidationError(
                    {"mappings": f"Program outcome at index {idx} does not exist."}
                )
            outcome_set = program_outcome.outcome_set
            if (
                outcome_set.program_id != syllabus.offering.program_id
                or outcome_set.version != syllabus.po_set_version
            ):
                raise ValidationError(
                    {
                        "mappings": (
                            f"Program outcome '{program_outcome.code}' does not belong"
                            " to the syllabus's bound PO-set version."
                        )
                    }
                )

            pair = (str(learning_outcome.pk), str(program_outcome.pk))
            if pair in seen_pairs:
                raise ValidationError(
                    {
                        "mappings": (
                            f"Duplicate mapping for learning outcome '{learning_outcome.code}'"
                            f" and program outcome '{program_outcome.code}'."
                        )
                    }
                )
            seen_pairs.add(pair)

            raw_weight = item.get("weight")
            if not isinstance(raw_weight, int) or isinstance(raw_weight, bool):
                raise ValidationError(
                    {
                        "mappings": (
                            f"LO-to-PO weight for '{learning_outcome.code}' ->"
                            f" '{program_outcome.code}' must be an integer between 0 and 5."
                        )
                    }
                )
            if raw_weight < 0 or raw_weight > 5:
                raise ValidationError(
                    {
                        "mappings": (
                            f"LO-to-PO weight for '{learning_outcome.code}' ->"
                            f" '{program_outcome.code}' must be between 0 and 5."
                        )
                    }
                )

            requested_active = bool(item.get("is_active", True))
            if raw_weight == 0 or not requested_active:
                weight = 0
                is_active = False
            else:
                weight = raw_weight
                is_active = True

            normalized.append(
                {
                    "learning_outcome": learning_outcome,
                    "program_outcome": program_outcome,
                    "weight": weight,
                    "is_active": is_active,
                }
            )
        return normalized

    @staticmethod
    def validate_mappings(*, syllabus, bound_po_set=None) -> dict:
        """Compute reachability, MAPPED/UNMAPPED LOs, ASSESSED/NOT_ASSESSED POs, and approval readiness."""
        from ..models import ProgramOutcomeSet

        if bound_po_set is None and syllabus.po_set_version is not None:
            bound_po_set = ProgramOutcomeSet.objects.filter(
                program_id=syllabus.offering.program_id,
                version=syllabus.po_set_version,
            ).first()

        los = list(syllabus.learning_outcomes.all().order_by("order", "created_at"))
        assessments = list(syllabus.assessments.all().order_by("order", "created_at"))
        active_assessment_ids = {a.pk for a in assessments if a.is_active}
        valid_assessment_ids = {a.pk for a in assessments}
        valid_lo_ids = {lo.pk for lo in los}

        a_lo_rows = list(
            syllabus.assessment_lo_mappings.select_related("assessment", "learning_outcome").all()
        )
        lo_po_rows = list(
            syllabus.lo_po_mappings.select_related(
                "learning_outcome", "program_outcome", "program_outcome__outcome_set"
            ).all()
        )

        errors: list[str] = []

        if not los or not assessments:
            errors.append("A syllabus version needs at least one LO and one assessment.")
        if bound_po_set is None:
            errors.append("Syllabus is not bound to a valid PO-set version for this program.")

        # Check endpoint integrity
        for m in a_lo_rows:
            if (
                m.assessment_id not in valid_assessment_ids
                or m.learning_outcome_id not in valid_lo_ids
            ):
                errors.append(
                    "Assessment-to-LO mapping references an endpoint outside this syllabus version."
                )
                break

        bound_pos = (
            list(bound_po_set.outcomes.all().order_by("ordering", "created_at"))
            if bound_po_set is not None
            else []
        )
        valid_po_ids = {po.pk for po in bound_pos}

        for m in lo_po_rows:
            if (
                m.learning_outcome_id not in valid_lo_ids
                or m.program_outcome_id not in valid_po_ids
            ):
                errors.append(
                    "LO-to-PO mapping references an endpoint outside this syllabus or bound PO-set version."
                )
                break

        # Compute A->LO totals per LO (only active assessments and active mappings with weight > 0)
        lo_assessment_weight: dict = {lo.pk: Decimal("0.00") for lo in los}
        for m in a_lo_rows:
            if (
                m.is_active
                and m.weight > 0
                and m.assessment_id in active_assessment_ids
                and m.learning_outcome_id in lo_assessment_weight
            ):
                lo_assessment_weight[m.learning_outcome_id] += m.weight

        # Compute positive active LO->PO links per LO and per PO
        lo_positive_po_links: dict[Any, list] = {lo.pk: [] for lo in los}
        po_positive_lo_links: dict[Any, list] = {po.pk: [] for po in bound_pos}
        for m in lo_po_rows:
            if (
                m.is_active
                and 1 <= m.weight <= 5
                and m.learning_outcome_id in lo_positive_po_links
                and m.program_outcome_id in po_positive_lo_links
            ):
                lo_positive_po_links[m.learning_outcome_id].append(m)
                po_positive_lo_links[m.program_outcome_id].append(m)

        lo_status_by_id: dict = {}
        lo_statuses: list[dict] = []
        unmapped_learning_outcomes: list[str] = []
        orphaned_learning_outcomes: list[str] = []

        for lo in los:
            total_w = lo_assessment_weight[lo.pk]
            status_val = "MAPPED" if total_w > 0 else "UNMAPPED"
            lo_status_by_id[lo.pk] = status_val
            po_count = len(lo_positive_po_links[lo.pk])

            if status_val == "UNMAPPED":
                unmapped_learning_outcomes.append(lo.code)
                if po_count > 0:
                    orphaned_learning_outcomes.append(lo.code)
            elif po_count == 0:
                orphaned_learning_outcomes.append(lo.code)

            lo_statuses.append(
                {
                    "learning_outcome_id": str(lo.pk),
                    "code": lo.code,
                    "status": status_val,
                    "total_assessment_weight": f"{total_w:.2f}",
                    "mapped_po_count": po_count,
                }
            )

        po_statuses: list[dict] = []
        unreachable_program_outcomes: list[str] = []
        assessed_po_count = 0

        for po in bound_pos:
            links = po_positive_lo_links[po.pk]
            reachable_links = [
                m for m in links if lo_status_by_id.get(m.learning_outcome_id) == "MAPPED"
            ]
            unreachable_links = [
                m for m in links if lo_status_by_id.get(m.learning_outcome_id) != "MAPPED"
            ]
            if reachable_links:
                po_status = "ASSESSED"
                assessed_po_count += 1
                total_lo_weight = sum(m.weight for m in reachable_links)
            else:
                po_status = "NOT_ASSESSED"
                total_lo_weight = 0
                if unreachable_links:
                    unreachable_program_outcomes.append(po.code)

            po_statuses.append(
                {
                    "program_outcome_id": str(po.pk),
                    "code": po.code,
                    "status": po_status,
                    "total_lo_weight": total_lo_weight,
                }
            )

        if unmapped_learning_outcomes:
            errors.append(
                "Unmapped learning outcomes (no positive active assessment weight): "
                + ", ".join(unmapped_learning_outcomes)
                + "."
            )
        if orphaned_learning_outcomes:
            errors.append(
                "Orphaned learning outcomes (incomplete assessment->LO->PO path): "
                + ", ".join(orphaned_learning_outcomes)
                + "."
            )
        if unreachable_program_outcomes:
            errors.append(
                "Unreachable program outcomes (linked only from unmapped LOs): "
                + ", ".join(unreachable_program_outcomes)
                + "."
            )
        if bound_pos and assessed_po_count == 0:
            errors.append(
                "At least one program outcome must be assessed by a mapped learning outcome."
            )

        return {
            "syllabus_id": str(syllabus.pk),
            "mapping_revision": syllabus.mapping_revision,
            "is_valid_for_approval": len(errors) == 0,
            "lo_statuses": lo_statuses,
            "po_statuses": po_statuses,
            "unmapped_learning_outcomes": unmapped_learning_outcomes,
            "orphaned_learning_outcomes": orphaned_learning_outcomes,
            "unreachable_program_outcomes": unreachable_program_outcomes,
            "errors": errors,
        }
>>>>>>> origin/main
