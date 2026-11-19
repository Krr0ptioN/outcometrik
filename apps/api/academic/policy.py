"""Enrollment eligibility and course-to-PO contribution weight governance policy.

The PRD marks withdrawn/incomplete handling and course-to-PO contribution weight
governance as *proposed* policies, so they live behind a version boundary.
Every enrollment records the policy version that produced its eligibility.
To change a rule, add a new version here; do not edit an old one silently.
"""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ValidationError

POLICY_VERSION = "proposed-v1"

# status -> counts toward outcome calculations?
ELIGIBILITY_BY_STATUS: dict[str, bool] = {
    "enrolled": True,
    "completed": True,
    "withdrawn": False,
    "incomplete": False,
}

# Course-to-PO contribution weight governance (CUR-03 / PRD §11.2 FR-204, §12)
COURSE_PO_WEIGHT_GOVERNANCE_CAPABILITY = "syllabus.approve"
COURSE_PO_WEIGHT_GOVERNANCE_ROLE = "program_coordinator"
COURSE_PO_WEIGHT_DEFAULT_LEVEL = "offering_syllabus_version"
MIN_COURSE_PO_WEIGHT = 1
MAX_COURSE_PO_WEIGHT = 5
CUMULATIVE_PO_QUANTIZE = Decimal("0.1")


def is_eligible(status: str) -> bool:
    return ELIGIBILITY_BY_STATUS[status]


def is_valid_course_po_weight(weight: object) -> bool:
    """Return True if weight is a strict integer in the range 1..5 inclusive."""
    return (
        isinstance(weight, int)
        and not isinstance(weight, bool)
        and MIN_COURSE_PO_WEIGHT <= weight <= MAX_COURSE_PO_WEIGHT
    )


def compute_cumulative_po_attainment(
    course_attainments: Iterable[tuple[Decimal | float | int, int]],
) -> Decimal | None:
    """Compute cumulative PO attainment across eligible approved course contributions.

    Given eligible approved `(course_po_score, weight)` pairs:
    - Each `weight` must be a strict integer between 1 and 5 inclusive.
    - If there are no eligible contributions, returns `None` (`NOT_ASSESSED`, never 0).
    - Otherwise computes sum(score * weight) / sum(weight) using Decimal arithmetic
      without intermediate rounding, quantized to 0.1 with ROUND_HALF_UP.
      Example: [(85, 5), (90, 3)] -> (85*5 + 90*3) / 8 = 695 / 8 = 86.875 -> Decimal("86.9").
    """
    numerator = Decimal(0)
    denominator = 0

    for score, weight in course_attainments:
        if not is_valid_course_po_weight(weight):
            raise ValidationError(
                {
                    "weight": (
                        f"Course-to-PO contribution weight must be an integer between "
                        f"{MIN_COURSE_PO_WEIGHT} and {MAX_COURSE_PO_WEIGHT}."
                    )
                }
            )
        if isinstance(score, bool) or score is None:
            raise ValidationError({"score": "Course PO score must be a valid numeric value."})
        try:
            score_dec = score if isinstance(score, Decimal) else Decimal(str(score))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValidationError(
                {"score": "Course PO score must be a valid numeric value."}
            ) from exc

        numerator += score_dec * Decimal(weight)
        denominator += weight

    if denominator == 0:
        return None

    raw = numerator / Decimal(denominator)
    return raw.quantize(CUMULATIVE_PO_QUANTIZE, rounding=ROUND_HALF_UP)
