# libs/modules/calc/calc/kernel.py
"""Deterministic Decimal scoring kernel (CALC-01).

Standard library only: no ORM, network, clock, or authorization dependency.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
)
from enum import Enum
from itertools import pairwise

KERNEL_VERSION = "1"

# Explicit context. Never depend on the thread-global decimal context.
CTX = Context(
    prec=40,
    rounding=ROUND_HALF_EVEN,
    Emin=-999,
    Emax=999,
    capitals=1,
    clamp=0,
    flags=[],
    traps=[InvalidOperation, DivisionByZero, Overflow],
)

# Display/export policy. PRD §12: one decimal, ROUND_HALF_UP, pending confirmation (DEC-01).
DISPLAY_QUANTUM = Decimal("0.1")
DISPLAY_ROUNDING = ROUND_HALF_UP

_ZERO = Decimal(0)
_HUNDRED = Decimal(100)
_PLAIN_DECIMAL = re.compile(r"-?[0-9]+(\.[0-9]+)?")


class ScoringInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def to_decimal(value: object, field: str) -> Decimal:
    """Accept str | int | Decimal. Reject float, bool, NaN, infinities."""
    if isinstance(value, (bool, float)):
        raise ScoringInputError("INVALID_NUMBER", f"{field}: float/bool not accepted")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, str):
        if not _PLAIN_DECIMAL.fullmatch(value):
            raise ScoringInputError("INVALID_NUMBER", f"{field}: {value!r}")
        d = Decimal(value)
    else:
        raise ScoringInputError("INVALID_NUMBER", f"{field}: unsupported type")
    if not d.is_finite():
        raise ScoringInputError("INVALID_NUMBER", f"{field}: not finite")
    return _ZERO if d == 0 else d  # collapses -0


def canonical_decimal(d: Decimal) -> str:
    """Plain string: no exponent, no trailing zeros, '0' for zero."""
    if d == 0:
        return "0"
    return format(d.normalize(CTX), "f")


def normalize_grade(points_earned: object, points_possible: object) -> Decimal | None:
    """100 * earned / possible. Returns None when points_possible == 0."""
    earned = to_decimal(points_earned, "points_earned")
    possible = to_decimal(points_possible, "points_possible")
    if earned < 0:
        raise ScoringInputError("NEGATIVE_GRADE", "points_earned < 0")
    if possible < 0:
        raise ScoringInputError("NEGATIVE_MAXIMUM", "points_possible < 0")
    if earned > possible:  # also catches possible == 0 with earned > 0
        raise ScoringInputError("GRADE_ABOVE_MAXIMUM", "points_earned > points_possible")
    if possible == 0:
        return None
    return CTX.divide(CTX.multiply(_HUNDRED, earned), possible)


class EntryState(str, Enum):
    SCORED = "SCORED"
    MISSING = "MISSING"
    EXEMPT = "EXEMPT"
    NOT_ASSESSED = "NOT_ASSESSED"


class ResultStatus(str, Enum):
    OK = "OK"
    INCOMPLETE = "INCOMPLETE"
    UNMAPPED = "UNMAPPED"
    NOT_ASSESSED = "NOT_ASSESSED"
    ALL_EXEMPT = "ALL_EXEMPT"


@dataclass(frozen=True)
class ScoreEntry:
    """One weighted input. Inputs are validated and coerced to Decimal on creation."""

    key: str
    weight: Decimal
    state: EntryState
    value: Decimal | None = None
    exempt_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.key:
            raise ScoringInputError("INVALID_KEY", "key must be non-empty")

        weight = to_decimal(self.weight, f"{self.key}.weight")
        if weight < 0:
            raise ScoringInputError("INVALID_WEIGHT", f"{self.key}: weight < 0")
        object.__setattr__(self, "weight", weight)

        if self.state is EntryState.SCORED:
            if self.value is None:
                raise ScoringInputError("INVALID_ENTRY", f"{self.key}: SCORED needs a value")
            value = to_decimal(self.value, f"{self.key}.value")
            if value < 0:
                raise ScoringInputError("NEGATIVE_GRADE", f"{self.key}: value < 0")
            if value > _HUNDRED:
                raise ScoringInputError("GRADE_ABOVE_MAXIMUM", f"{self.key}: value > 100")
            object.__setattr__(self, "value", value)
        elif self.value is not None:
            raise ScoringInputError("INVALID_ENTRY", f"{self.key}: {self.state.value} has no value")

        if self.state is EntryState.EXEMPT:
            if not (self.exempt_reason and self.exempt_reason.strip()):
                raise ScoringInputError("EXEMPT_REASON_REQUIRED", f"{self.key}: reason required")
        elif self.exempt_reason is not None:
            raise ScoringInputError("INVALID_ENTRY", f"{self.key}: reason only for EXEMPT")


def grade_entry(
    key: str, weight: object, points_earned: object | None, points_possible: object
) -> ScoreEntry:
    """Build an entry from raw points. points_earned=None means the required grade is missing.

    An explicit 0 is a real score and is never treated as missing.
    """
    possible = to_decimal(points_possible, f"{key}.points_possible")
    if points_earned is None:
        return ScoreEntry(key, weight, EntryState.MISSING)  # type: ignore[arg-type]
    value = normalize_grade(points_earned, possible)
    if value is None:
        return ScoreEntry(key, weight, EntryState.NOT_ASSESSED)  # type: ignore[arg-type]
    return ScoreEntry(key, weight, EntryState.SCORED, value)  # type: ignore[arg-type]


def exempt_entry(key: str, weight: object, reason: str) -> ScoreEntry:
    """The reason is required here. Whether the caller may exempt is an adapter/service concern."""
    return ScoreEntry(key, weight, EntryState.EXEMPT, None, reason)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Contribution:
    key: str
    weight: Decimal
    value: Decimal


@dataclass(frozen=True)
class ScoreResult:
    status: ResultStatus
    value: Decimal | None  # full precision, never display-rounded
    total_weight: Decimal  # the denominator (sum of participating weights)
    contributions: tuple[Contribution, ...] = ()
    missing: tuple[str, ...] = ()
    exemptions: tuple[tuple[str, str], ...] = ()

    def display(self) -> str | None:
        return None if self.value is None else display_value(self.value)

    def canonical(self) -> dict:
        return {
            "kernel_version": KERNEL_VERSION,
            "status": self.status.value,
            "value": None if self.value is None else canonical_decimal(self.value),
            "total_weight": canonical_decimal(self.total_weight),
            "contributions": [
                {
                    "key": c.key,
                    "weight": canonical_decimal(c.weight),
                    "value": canonical_decimal(c.value),
                }
                for c in self.contributions
            ],
            "missing": list(self.missing),
            "exemptions": [{"key": k, "reason": r} for k, r in self.exemptions],
        }

    def canonical_json(self) -> str:
        return json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))


def weighted_mean(entries: Iterable[ScoreEntry]) -> ScoreResult:
    """score = sum(weight * value) / sum(weight) over eligible (weight > 0) entries.

    Used for LO (from assessments), course PO (from LOs) and cumulative PO (from courses).
    Entries are processed in key order, so the caller's order cannot change the result.
    Intermediate values are never rounded to display precision.
    """
    items = tuple(sorted(entries, key=lambda e: e.key))

    for previous, current in pairwise(items):
        if previous.key == current.key:
            raise ScoringInputError("DUPLICATE_KEY", current.key)

    eligible = [e for e in items if e.weight > 0]
    if not eligible:
        return ScoreResult(ResultStatus.UNMAPPED, None, _ZERO)

    exemptions = tuple(
        (e.key, e.exempt_reason or "") for e in eligible if e.state is EntryState.EXEMPT
    )
    missing = tuple(e.key for e in eligible if e.state is EntryState.MISSING)
    if missing:
        return ScoreResult(
            ResultStatus.INCOMPLETE, None, _ZERO, missing=missing, exemptions=exemptions
        )

    scored = [e for e in eligible if e.state is EntryState.SCORED]
    if not scored:
        all_exempt = all(e.state is EntryState.EXEMPT for e in eligible)
        status = ResultStatus.ALL_EXEMPT if all_exempt else ResultStatus.NOT_ASSESSED
        return ScoreResult(status, None, _ZERO, exemptions=exemptions)

    numerator = _ZERO
    denominator = _ZERO
    for e in scored:
        assert e.value is not None
        numerator = CTX.add(numerator, CTX.multiply(e.weight, e.value))
        denominator = CTX.add(denominator, e.weight)

    return ScoreResult(
        ResultStatus.OK,
        CTX.divide(numerator, denominator),
        denominator,
        contributions=tuple(Contribution(e.key, e.weight, e.value) for e in scored),  # type: ignore[arg-type]
        exemptions=exemptions,
    )


def entry_from_result(key: str, weight: object, result: ScoreResult) -> ScoreEntry:
    """Promote a lower-level result (LO, course PO) to an input of the next level.

    OK -> SCORED, INCOMPLETE -> MISSING (blocks upward), ALL_EXEMPT -> EXEMPT,
    UNMAPPED / NOT_ASSESSED -> NOT_ASSESSED (excluded from the denominator).
    """
    if result.status is ResultStatus.OK:
        return ScoreEntry(key, weight, EntryState.SCORED, result.value)  # type: ignore[arg-type]
    if result.status is ResultStatus.INCOMPLETE:
        return ScoreEntry(key, weight, EntryState.MISSING)  # type: ignore[arg-type]
    if result.status is ResultStatus.ALL_EXEMPT:
        reason = "; ".join(f"{k}: {r}" for k, r in result.exemptions)
        return ScoreEntry(key, weight, EntryState.EXEMPT, None, reason)  # type: ignore[arg-type]
    return ScoreEntry(key, weight, EntryState.NOT_ASSESSED)  # type: ignore[arg-type]


compute_lo = weighted_mean
compute_course_po = weighted_mean
compute_cumulative_po = weighted_mean


# Display/export rounding. This is the ONLY place a value is rounded.
def quantize_display(value: Decimal) -> Decimal:
    return value.quantize(DISPLAY_QUANTUM, rounding=DISPLAY_ROUNDING, context=CTX)


def display_value(value: Decimal) -> str:
    return format(quantize_display(value), "f")
