"""Immutable report data handed to the CSV and PDF writers.

These are plain value objects. They are built by a publication reader from stored,
published records; writers never query the database.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID


class ResultState(StrEnum):
    """Why a value is, or is not, a number. A missing value is never a zero."""

    MEASURED = "MEASURED"
    NOT_ASSESSED = "NOT_ASSESSED"
    UNMAPPED = "UNMAPPED"
    INCOMPLETE = "INCOMPLETE"
    EXEMPT = "EXEMPT"


STATE_LABELS = {
    ResultState.MEASURED: "Measured",
    ResultState.NOT_ASSESSED: "Not assessed",
    ResultState.UNMAPPED: "Unmapped",
    ResultState.INCOMPLETE: "Incomplete",
    ResultState.EXEMPT: "Exempt",
}


@dataclass(frozen=True)
class EvidenceInput:
    label: str
    source_revision: str
    weight: Decimal
    value: Decimal | None
    state: ResultState


@dataclass(frozen=True)
class Evidence:
    """How one result was produced: formula path, numerator, denominator and inputs."""

    formula: str
    numerator: Decimal | None
    denominator: Decimal | None
    inputs: tuple[EvidenceInput, ...] = ()


@dataclass(frozen=True)
class OutcomeRow:
    code: str
    title: str
    value: Decimal | None
    state: ResultState
    sample_size: int
    population_size: int | None = None
    evidence: Evidence | None = None


@dataclass(frozen=True)
class ReportHeader:
    publication_id: UUID
    run_id: UUID
    program: str
    term: str
    po_set_version: str
    policy_version: str
    scope_label: str
    population: str
    sample_size: int
    coverage: str
    published_at: datetime
    stale: bool = False


@dataclass(frozen=True)
class Report:
    kind: Literal["student", "cohort"]
    header: ReportHeader
    rows: tuple[OutcomeRow, ...]
    # Access scope ids the data was drawn from, taken from stored records (never from the
    # request). Authorization is checked against these.
    scope_ids: tuple[UUID, ...]


_ONE_DECIMAL = Decimal("0.1")


def format_score(value: Decimal | None) -> str:
    """One decimal, ROUND_HALF_UP, applied only at display/export (PRD §4). None is blank."""
    if value is None:
        return ""
    return str(value.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP))


def format_exact(value: Decimal | None) -> str:
    """Full precision for evidence values, so a result can be re-derived by hand."""
    if value is None:
        return ""
    return format(value, "f")


def count_lines(report: Report, *, include_evidence: bool) -> int:
    """Rows an export will contain; used to bound export size."""
    total = len(report.rows)
    if include_evidence:
        total += sum(max(len(r.evidence.inputs), 1) for r in report.rows if r.evidence)
    return total
