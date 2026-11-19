"""The seam between exports and published results.

Exports read immutable published data only through `PublicationReader`.
`AcademicPublicationReader` bridges to the CALC-03 publication store and ANA-01 cohort
analytics without mutating publications or calculation runs.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from academic.models import CalculationRun, Enrollment, OutcomeScore, Publication
from academic.services.analytics import CohortAnalyticsService
from academic.services.publications import PublicationService

from .domain import (
    Evidence,
    EvidenceInput,
    OutcomeRow,
    Report,
    ReportHeader,
    ResultState,
)

_STATUS_MAP: dict[str, ResultState] = {
    OutcomeScore.Status.OK: ResultState.MEASURED,
    "MEASURED": ResultState.MEASURED,
    "scored": ResultState.MEASURED,
    OutcomeScore.Status.NOT_ASSESSED: ResultState.NOT_ASSESSED,
    OutcomeScore.Status.UNMAPPED: ResultState.UNMAPPED,
    OutcomeScore.Status.INCOMPLETE: ResultState.INCOMPLETE,
    "missing": ResultState.INCOMPLETE,
    "incomplete": ResultState.INCOMPLETE,
    OutcomeScore.Status.ALL_EXEMPT: ResultState.EXEMPT,
    "EXEMPT": ResultState.EXEMPT,
    "exempt": ResultState.EXEMPT,
}


def _map_status(raw: str | None) -> ResultState:
    if raw is None:
        return ResultState.NOT_ASSESSED
    return _STATUS_MAP.get(str(raw), ResultState.NOT_ASSESSED)


def _to_decimal(raw) -> Decimal | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, Decimal):
        return raw
    return Decimal(str(raw))


def _term_label(publication: Publication) -> str:
    term = publication.term or (
        publication.offering.term if publication.offering_id is not None else None
    )
    if term is not None:
        return f"{term.year} {term.season.title()}"
    return "Cumulative"


def _scope_label(publication: Publication) -> str:
    if publication.offering_id is not None:
        return f"{publication.offering.course.code}-{publication.offering.section} (offering)"
    return f"{publication.program.title} (program)"


def _program_label(publication: Publication) -> str:
    return f"{publication.program.code} — {publication.program.title}"


def _student_scope_ids(
    publication: Publication, student, scores: list[OutcomeScore]
) -> tuple[UUID, ...]:
    ids: set[UUID] = set()
    if publication.offering_id is not None:
        ids.add(publication.offering_id)
    for score in scores:
        if score.offering_id is not None:
            ids.add(score.offering_id)
        for item in (score.evidence or {}).get("contributions", []):
            raw_off_id = item.get("offering_id")
            if raw_off_id:
                ids.add(UUID(str(raw_off_id)))
    student_key = str(student.pk)
    for off in (publication.run.manifest or {}).get("offerings") or []:
        raw_off_id = off.get("id")
        if not raw_off_id:
            continue
        if any(str(enr.get("student_id")) == student_key for enr in off.get("enrollments") or []):
            ids.add(UUID(str(raw_off_id)))
    if not ids:
        ids.update(
            Enrollment.objects.filter(
                student=student, offering__program_id=publication.program_id
            ).values_list("offering_id", flat=True)
        )
    return tuple(sorted(ids))


def _build_student_evidence(score: OutcomeScore) -> Evidence:
    raw = score.evidence or {}
    if score.level == OutcomeScore.Level.COURSE_PO:
        formula = "sum(weight * LO) / sum(weight)"
    elif score.level == OutcomeScore.Level.CUMULATIVE_PO:
        formula = "sum(weight * Course PO) / sum(weight)"
    else:
        formula = "sum(weight * Assessment) / sum(weight)"

    inputs: list[EvidenceInput] = []
    for item in raw.get("contributions") or []:
        if "course_code" in item:
            term = item.get("term")
            label = f"{item['course_code']} ({term})" if term else str(item["course_code"])
            syl_ver = item.get("syllabus_version")
            source_revision = f"syllabus-v{syl_ver}" if syl_ver is not None else "published"
            val_raw = (
                item.get("value") if item.get("value") is not None else item.get("course_po_value")
            )
            state = _map_status(item.get("course_po_status", OutcomeScore.Status.OK))
        elif "lo_code" in item:
            label = str(item["lo_code"])
            syl_ver = item.get("syllabus_version") or raw.get("syllabus_version")
            source_revision = f"syllabus-v{syl_ver}" if syl_ver is not None else "published"
            val_raw = item.get("value") if item.get("value") is not None else item.get("lo_value")
            state = _map_status(item.get("lo_status", OutcomeScore.Status.OK))
        else:
            label = str(item.get("assessment_code") or item.get("label") or "input")
            syl_ver = item.get("syllabus_version") or raw.get("syllabus_version")
            source_revision = f"syllabus-v{syl_ver}" if syl_ver is not None else "published"
            val_raw = item.get("normalized_score")
            state = _map_status(item.get("state", OutcomeScore.Status.OK))

        inputs.append(
            EvidenceInput(
                label=label,
                source_revision=source_revision,
                weight=_to_decimal(item.get("weight")) or Decimal(0),
                value=_to_decimal(val_raw),
                state=state,
            )
        )

    return Evidence(
        formula=formula,
        numerator=score.numerator,
        denominator=score.denominator,
        inputs=tuple(inputs),
    )


def _cohort_row_state(item: dict) -> tuple[Decimal | None, ResultState]:
    sample_n = int(item.get("n", 0))
    mean_raw = item.get("mean")
    if sample_n > 0 and mean_raw is not None:
        return Decimal(str(mean_raw)), ResultState.MEASURED
    exclusions = item.get("exclusions") or {}
    if exclusions.get(OutcomeScore.Status.INCOMPLETE, 0) > 0:
        return None, ResultState.INCOMPLETE
    if exclusions.get(OutcomeScore.Status.ALL_EXEMPT, 0) > 0:
        return None, ResultState.EXEMPT
    if exclusions.get(OutcomeScore.Status.UNMAPPED, 0) > 0:
        return None, ResultState.UNMAPPED
    return None, ResultState.NOT_ASSESSED


class PublicationReader(Protocol):
    """Reads immutable, published data. Must never return unpublished or draft data."""

    def student_report(self, *, publication_id: UUID, student) -> Report | None:
        """The given student's own report, or None if it does not exist or is not published."""

    def cohort_report(self, *, publication_id: UUID, program_id: UUID) -> Report | None:
        """A program cohort report, or None if it does not exist or is not published."""


class AcademicPublicationReader:
    """Reads immutable CALC-03 publications and ANA-01 cohort analytics."""

    def __init__(
        self,
        *,
        publication_service: PublicationService | None = None,
        analytics_service: CohortAnalyticsService | None = None,
    ):
        self.publication_service = publication_service or PublicationService()
        self.analytics_service = analytics_service or CohortAnalyticsService(
            publication_service=self.publication_service
        )

    def student_report(self, *, publication_id: UUID, student) -> Report | None:
        publication = (
            Publication.objects.select_related(
                "program",
                "offering__course",
                "offering__term",
                "term",
                "run",
            )
            .filter(pk=publication_id, audience=Publication.Audience.STUDENT)
            .first()
        )
        if publication is None:
            return None

        level = (
            OutcomeScore.Level.COURSE_PO
            if publication.run.scope_kind == CalculationRun.ScopeKind.OFFERING
            else OutcomeScore.Level.CUMULATIVE_PO
        )
        scores = list(
            publication.run.scores.filter(level=level, student=student)
            .select_related("program_outcome", "offering")
            .order_by("program_outcome__ordering", "outcome_code", "id")
        )
        if not scores:
            return None

        rows: list[OutcomeRow] = []
        for score in scores:
            state = _map_status(score.status)
            raw_exact = (score.evidence or {}).get("exact_value")
            if state == ResultState.MEASURED:
                value = _to_decimal(raw_exact) if raw_exact is not None else score.value
            else:
                value = None
            title = score.program_outcome.label if score.program_outcome_id else score.outcome_code
            rows.append(
                OutcomeRow(
                    code=score.outcome_code,
                    title=title,
                    value=value,
                    state=state,
                    sample_size=1 if state == ResultState.MEASURED else 0,
                    population_size=1,
                    evidence=_build_student_evidence(score),
                )
            )

        measured_count = sum(1 for row in rows if row.state == ResultState.MEASURED)
        stale = self.publication_service.is_stale(publication=publication)
        header = ReportHeader(
            publication_id=publication.pk,
            run_id=publication.run_id,
            program=_program_label(publication),
            term=_term_label(publication),
            po_set_version=f"PO-set v{publication.po_set_version}",
            policy_version=publication.run.policy_version,
            scope_label=_scope_label(publication),
            population="Individual student",
            sample_size=1 if measured_count > 0 else 0,
            coverage=f"{measured_count} of {len(rows)} outcomes measured",
            published_at=publication.published_at,
            stale=stale,
        )
        scope_ids = _student_scope_ids(publication, student, scores)
        return Report(kind="student", header=header, rows=tuple(rows), scope_ids=scope_ids)

    def cohort_report(self, *, publication_id: UUID, program_id: UUID) -> Report | None:
        publication = (
            Publication.objects.select_related(
                "program",
                "offering__course",
                "offering__term",
                "term",
                "run",
            )
            .filter(pk=publication_id, program_id=program_id)
            .first()
        )
        if publication is None:
            return None

        summary = self.analytics_service.cohort_summary(publication=publication)
        rows: list[OutcomeRow] = []
        for item in summary["outcomes"]:
            value, state = _cohort_row_state(item)
            sample_n = int(item["n"])
            population_size = int(item["population_size"])
            rows.append(
                OutcomeRow(
                    code=item["code"],
                    title=item["label"],
                    value=value,
                    state=state,
                    sample_size=sample_n,
                    population_size=population_size,
                    evidence=Evidence(
                        formula="mean(measured student PO scores)",
                        numerator=None,
                        denominator=Decimal(sample_n) if sample_n > 0 else None,
                        inputs=(),
                    ),
                )
            )

        stale = summary["publication_status"] == "stale"
        header = ReportHeader(
            publication_id=publication.pk,
            run_id=publication.run_id,
            program=_program_label(publication),
            term=_term_label(publication),
            po_set_version=f"PO-set v{publication.po_set_version}",
            policy_version=summary["policy_version"],
            scope_label=_scope_label(publication),
            population=f"{summary['population_size']} eligible students ({publication.audience} publication)",
            sample_size=int(summary["sample_size"]),
            coverage=summary["coverage"],
            published_at=publication.published_at,
            stale=stale,
        )
        return Report(kind="cohort", header=header, rows=tuple(rows), scope_ids=(program_id,))


class UnavailablePublicationReader:
    """Fallback reader that reports every publication as not found."""

    def student_report(self, *, publication_id, student):
        return None

    def cohort_report(self, *, publication_id, program_id):
        return None
