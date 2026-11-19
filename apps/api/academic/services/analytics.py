"""Read-only cohort analytics and PO-set-safe trend comparison service (ANA-01)."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from access.policy import AuthorizationService
from calc.kernel import CTX, DISPLAY_QUANTUM, DISPLAY_ROUNDING
from django.core.exceptions import ValidationError
from django.http import Http404
from wireup import injectable

from .. import scoping
from ..models import (
    CalculationRun,
    OutcomeScore,
    ProgramOutcomeSet,
    Publication,
)
from .publications import PublicationService

_ZERO = Decimal(0)
_TWO = Decimal(2)
_COVERAGE_QUANTUM = Decimal("0.0001")
_BUCKET_50 = Decimal(50)
_BUCKET_70 = Decimal(70)
_BUCKET_85 = Decimal(85)

_EXCLUSION_STATUSES = (
    OutcomeScore.Status.NOT_ASSESSED,
    OutcomeScore.Status.INCOMPLETE,
    OutcomeScore.Status.ALL_EXEMPT,
    OutcomeScore.Status.UNMAPPED,
)


def _format_display(value: Decimal | None) -> str | None:
    if value is None:
        return None
    quantized = value.quantize(DISPLAY_QUANTUM, rounding=DISPLAY_ROUNDING, context=CTX)
    return format(quantized, "f")


def _format_coverage(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0000"
    ratio = CTX.divide(Decimal(numerator), Decimal(denominator))
    quantized = ratio.quantize(_COVERAGE_QUANTUM, rounding=ROUND_HALF_UP, context=CTX)
    return format(quantized, "f")


def _parse_uuid(value: Any, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value).strip())
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({field_name: f"Invalid UUID for {field_name}."}) from exc


def _empty_exclusions() -> dict[str, int]:
    return {str(status): 0 for status in _EXCLUSION_STATUSES}


def _compute_distribution(values: list[Decimal]) -> dict[str, int]:
    buckets = {
        "<50": 0,
        "50-69.9": 0,
        "70-84.9": 0,
        "85-100": 0,
    }
    for val in values:
        if val < _BUCKET_50:
            buckets["<50"] += 1
        elif val < _BUCKET_70:
            buckets["50-69.9"] += 1
        elif val < _BUCKET_85:
            buckets["70-84.9"] += 1
        else:
            buckets["85-100"] += 1
    return buckets


def _compute_median(sorted_values: list[Decimal]) -> Decimal | None:
    count = len(sorted_values)
    if count == 0:
        return None
    mid = count // 2
    if count % 2 == 1:
        return sorted_values[mid]
    return CTX.divide(CTX.add(sorted_values[mid - 1], sorted_values[mid]), _TWO)


def _compute_mean(values: list[Decimal]) -> Decimal | None:
    count = len(values)
    if count == 0:
        return None
    total = _ZERO
    for val in values:
        total = CTX.add(total, val)
    return CTX.divide(total, Decimal(count))


@injectable
class CohortAnalyticsService:
    """Read-only cohort statistics and trend analytics over immutable published outcomes."""

    model = Publication

    def __init__(
        self,
        auth_service: AuthorizationService | None = None,
        publication_service: PublicationService | None = None,
        *,
        actor: Any = None,
    ):
        self.auth_service = auth_service or AuthorizationService()
        self.publication_service = publication_service or PublicationService(
            auth_service=self.auth_service
        )
        self.actor = actor

    def get_visible_publications(self, *, actor: Any = None, **filters):
        """Return publications visible to staff actors with outcomes.view or publication access."""
        effective_actor = actor if actor is not None else self.actor
        if effective_actor is None or not getattr(effective_actor, "is_authenticated", False):
            return Publication.objects.none()
        qs = self.publication_service.get_queryset(actor=effective_actor, **filters)
        program_ids, offering_ids = scoping._staff_publication_scope_ids(effective_actor)
        if not program_ids and not offering_ids:
            return Publication.objects.none()
        return qs

    def resolve_publication(
        self,
        *,
        actor: Any,
        publication_id: Any = None,
        program_id: Any = None,
        course_id: Any = None,
        term_id: Any = None,
        audience: str | None = None,
    ) -> Publication:
        """Resolve a single authorized publication by ID or latest publication for a program."""
        qs = self.get_visible_publications(actor=actor)
        if audience:
            qs = qs.filter(audience=audience)

        parsed_program_id = _parse_uuid(program_id, "program_id") if program_id else None
        parsed_course_id = _parse_uuid(course_id, "course_id") if course_id else None
        parsed_term_id = _parse_uuid(term_id, "term_id") if term_id else None

        if publication_id:
            parsed_pub_id = _parse_uuid(publication_id, "publication_id")
            if parsed_program_id is not None:
                qs = qs.filter(program_id=parsed_program_id)
            publication = qs.filter(pk=parsed_pub_id).first()
            if publication is None:
                raise Http404("Publication not found.")
            return publication

        if parsed_program_id is None:
            raise ValidationError(
                {"program_id": "Either publication_id or program_id is required."}
            )

        program_qs = qs.filter(program_id=parsed_program_id)

        # Prefer narrowest matching publication when course_id or term_id is specified,
        # falling back to the latest program-level publication.
        candidate_qs = program_qs
        if parsed_course_id is not None:
            course_matches = candidate_qs.filter(offering__course_id=parsed_course_id)
            if course_matches.exists():
                candidate_qs = course_matches
        if parsed_term_id is not None:
            term_matches = candidate_qs.filter(term_id=parsed_term_id)
            if not term_matches.exists():
                term_matches = candidate_qs.filter(offering__term_id=parsed_term_id)
            if term_matches.exists():
                candidate_qs = term_matches

        publication = candidate_qs.order_by("-published_at", "-series_version", "id").first()
        if publication is None:
            raise Http404("No published outcomes found for the requested scope.")
        return publication

    def resolve_publications_for_trends(
        self,
        *,
        actor: Any,
        publication_ids: list[Any] | None = None,
        program_id: Any = None,
        po_set_version: Any = None,
        audience: str | None = None,
        course_id: Any = None,
    ) -> list[Publication]:
        """Resolve authorized publications for cross-term / cross-cohort trend comparison."""
        qs = self.get_visible_publications(actor=actor)
        if audience:
            qs = qs.filter(audience=audience)

        if publication_ids:
            parsed_ids: list[uuid.UUID] = []
            seen: set[uuid.UUID] = set()
            for raw_id in publication_ids:
                uid = _parse_uuid(raw_id, "publication_ids")
                if uid not in seen:
                    seen.add(uid)
                    parsed_ids.append(uid)

            found = list(qs.filter(pk__in=parsed_ids))
            if len(found) != len(parsed_ids):
                raise Http404("One or more requested publications were not found.")
            if program_id is not None:
                parsed_program_id = _parse_uuid(program_id, "program_id")
                if any(pub.program_id != parsed_program_id for pub in found):
                    raise ValidationError(
                        "Cannot compare publications from different programs.",
                        code="incompatible_po_set_version",
                    )
            return found

        if program_id is None:
            raise ValidationError(
                {"program_id": "Either publication_ids or program_id is required."}
            )

        parsed_program_id = _parse_uuid(program_id, "program_id")
        qs = qs.filter(program_id=parsed_program_id)
        if po_set_version not in (None, ""):
            try:
                qs = qs.filter(po_set_version=int(po_set_version))
            except (ValueError, TypeError) as exc:
                raise ValidationError(
                    {"po_set_version": "po_set_version must be an integer."}
                ) from exc
        if course_id:
            parsed_course_id = _parse_uuid(course_id, "course_id")
            qs = qs.filter(offering__course_id=parsed_course_id)

        publications = list(qs)
        if not publications:
            raise Http404("No published outcomes found for the requested scope.")
        return publications

    def _filtered_po_scores(
        self,
        *,
        publication: Publication,
        course_id: Any = None,
        term_id: Any = None,
    ) -> list[OutcomeScore]:
        """Read immutable PO-level OutcomeScore rows for a publication with optional filters."""
        parsed_course_id = _parse_uuid(course_id, "course_id") if course_id else None
        parsed_term_id = _parse_uuid(term_id, "term_id") if term_id else None

        run = publication.run
        if run.scope_kind == CalculationRun.ScopeKind.OFFERING:
            qs = run.scores.filter(level=OutcomeScore.Level.COURSE_PO).select_related(
                "offering", "program_outcome"
            )
            if parsed_course_id is not None:
                qs = qs.filter(offering__course_id=parsed_course_id)
            if parsed_term_id is not None:
                qs = qs.filter(offering__term_id=parsed_term_id)
            return list(qs.order_by("outcome_code", "id"))

        # Program-scoped (cumulative PO) publication
        qs = run.scores.filter(level=OutcomeScore.Level.CUMULATIVE_PO).select_related(
            "offering", "program_outcome"
        )
        if parsed_course_id is None and parsed_term_id is None:
            return list(qs.order_by("outcome_code", "id"))

        manifest_offerings = (run.manifest or {}).get("offerings") or []
        if manifest_offerings:
            matching_student_ids: set[str] = set()
            for off in manifest_offerings:
                if parsed_course_id is not None and str(off.get("course_id")) != str(
                    parsed_course_id
                ):
                    continue
                if parsed_term_id is not None and str(off.get("term_id")) != str(parsed_term_id):
                    continue
                for enr in off.get("enrollments") or []:
                    if enr.get("eligible_for_outcomes") and enr.get("student_id"):
                        matching_student_ids.add(str(enr["student_id"]))
            if not matching_student_ids:
                return []
            return list(
                qs.filter(student_id__in=matching_student_ids).order_by("outcome_code", "id")
            )

        # Fallback if manifest has no offerings list (e.g. minimal fixture)
        if (
            parsed_term_id is not None
            and publication.term_id is not None
            and publication.term_id != parsed_term_id
        ):
            return []

        rows = list(qs.order_by("outcome_code", "id"))
        if parsed_course_id is not None:
            target = str(parsed_course_id)
            rows = [
                row
                for row in rows
                if (row.offering_id is not None and str(row.offering.course_id) == target)
                or any(
                    str(c.get("course_id")) == target
                    for c in (row.evidence or {}).get("contributions", [])
                )
            ]
        return rows

    def cohort_summary(
        self,
        *,
        publication: Publication,
        course_id: Any = None,
        term_id: Any = None,
    ) -> dict[str, Any]:
        """Compute read-only per-PO cohort distributions and coverage over a publication."""
        publication = Publication.objects.select_related(
            "program", "offering__term", "term", "run"
        ).get(pk=publication.pk)

        rows = self._filtered_po_scores(
            publication=publication,
            course_id=course_id,
            term_id=term_id,
        )

        # Resolve canonical PO ordering from the publication's bound ProgramOutcomeSet.
        po_set = (
            ProgramOutcomeSet.objects.filter(
                program_id=publication.program_id,
                version=publication.po_set_version,
            )
            .prefetch_related("outcomes")
            .first()
        )
        po_entries: list[tuple[str | None, str, str]] = []
        seen_codes: set[str] = set()
        if po_set is not None:
            for po in po_set.outcomes.order_by("ordering", "id"):
                po_entries.append((str(po.pk), po.code, po.label))
                seen_codes.add(po.code)

        rows_by_code: dict[str, list[OutcomeScore]] = {}
        for row in rows:
            rows_by_code.setdefault(row.outcome_code, []).append(row)
            if row.outcome_code not in seen_codes:
                label = row.program_outcome.label if row.program_outcome_id else row.outcome_code
                po_id = str(row.program_outcome_id) if row.program_outcome_id else None
                po_entries.append((po_id, row.outcome_code, label))
                seen_codes.add(row.outcome_code)

        outcomes_summary: list[dict[str, Any]] = []
        total_exclusions = _empty_exclusions()
        total_scored_rows = 0
        total_eligible_rows = 0

        for po_id, po_code, po_label in po_entries:
            po_rows = rows_by_code.get(po_code, [])
            population_size = len(po_rows)
            scored_values: list[Decimal] = []
            po_exclusions = _empty_exclusions()

            for row in po_rows:
                if row.status == OutcomeScore.Status.OK and row.value is not None:
                    scored_values.append(row.value)
                else:
                    status_key = str(row.status)
                    if status_key in po_exclusions:
                        po_exclusions[status_key] += 1
                        total_exclusions[status_key] += 1

            scored_values.sort()
            sample_n = len(scored_values)
            total_scored_rows += sample_n
            total_eligible_rows += population_size

            mean_val = _compute_mean(scored_values)
            median_val = _compute_median(scored_values)
            min_val = scored_values[0] if scored_values else None
            max_val = scored_values[-1] if scored_values else None

            outcomes_summary.append(
                {
                    "program_outcome_id": po_id,
                    "code": po_code,
                    "label": po_label,
                    "n": sample_n,
                    "population_size": population_size,
                    "coverage": _format_coverage(sample_n, population_size),
                    "mean": _format_display(mean_val),
                    "median": _format_display(median_val),
                    "min": _format_display(min_val),
                    "max": _format_display(max_val),
                    "distribution": _compute_distribution(scored_values),
                    "exclusions": po_exclusions,
                }
            )

        distinct_population_students = {row.student_id for row in rows}
        distinct_scored_students = {
            row.student_id
            for row in rows
            if row.status == OutcomeScore.Status.OK and row.value is not None
        }

        effective_term = publication.term or (
            publication.offering.term if publication.offering_id is not None else None
        )
        is_stale = self.publication_service.is_stale(publication=publication)

        return {
            "publication_id": str(publication.pk),
            "run_id": str(publication.run_id),
            "series_version": publication.series_version,
            "program_id": str(publication.program_id),
            "offering_id": str(publication.offering_id)
            if publication.offering_id is not None
            else None,
            "term_id": str(effective_term.pk) if effective_term is not None else None,
            "po_set_version": publication.po_set_version,
            "policy_version": publication.run.policy_version,
            "engine_version": publication.run.engine_version,
            "publication_status": "stale" if is_stale else "published",
            "audience": publication.audience,
            "published_at": publication.published_at.isoformat()
            if publication.published_at
            else None,
            "filters": {
                "course_id": str(_parse_uuid(course_id, "course_id")) if course_id else None,
                "term_id": str(_parse_uuid(term_id, "term_id")) if term_id else None,
            },
            "sample_size": len(distinct_scored_students),
            "population_size": len(distinct_population_students),
            "coverage": _format_coverage(total_scored_rows, total_eligible_rows),
            "exclusions": total_exclusions,
            "outcomes": outcomes_summary,
        }

    def compare_trends(self, *, publications: list[Publication]) -> dict[str, Any]:
        """Compare compatible publications across terms/cohorts.

        Refuses to compare publications from different programs or different PO-set versions.
        """
        if not publications:
            raise ValidationError(
                "At least one publication is required to compare trends.",
                code="empty_publications",
            )

        loaded = list(
            Publication.objects.select_related("program", "offering__term", "term", "run").filter(
                pk__in=[pub.pk for pub in publications]
            )
        )
        if not loaded:
            raise ValidationError(
                "At least one publication is required to compare trends.",
                code="empty_publications",
            )

        program_ids = {pub.program_id for pub in loaded}
        if len(program_ids) > 1:
            raise ValidationError(
                "Cannot compare publications from different programs.",
                code="incompatible_po_set_version",
            )

        po_set_versions = {pub.po_set_version for pub in loaded}
        if len(po_set_versions) > 1:
            raise ValidationError(
                "Cannot compare publications with different PO-set versions; "
                "changed PO definitions are not a performance trend.",
                code="incompatible_po_set_version",
            )

        def _sort_key(pub: Publication):
            term = pub.term or (pub.offering.term if pub.offering_id is not None else None)
            starts_at = term.starts_at if term is not None else dt.date.min
            published_at = (
                pub.published_at
                if pub.published_at is not None
                else dt.datetime.min.replace(tzinfo=dt.UTC)
            )
            return (starts_at, published_at, pub.series_version, str(pub.pk))

        ordered = sorted(loaded, key=_sort_key)
        points: list[dict[str, Any]] = []
        for pub in ordered:
            summary = self.cohort_summary(publication=pub)
            term = pub.term or (pub.offering.term if pub.offering_id is not None else None)
            term_payload = (
                {
                    "id": str(term.pk),
                    "year": term.year,
                    "season": term.season,
                    "label": f"{term.year}-{term.season}",
                }
                if term is not None
                else None
            )
            points.append(
                {
                    "publication_id": summary["publication_id"],
                    "run_id": summary["run_id"],
                    "term": term_payload,
                    "term_id": summary["term_id"],
                    "po_set_version": summary["po_set_version"],
                    "series_version": summary["series_version"],
                    "policy_version": summary["policy_version"],
                    "publication_status": summary["publication_status"],
                    "published_at": summary["published_at"],
                    "sample_size": summary["sample_size"],
                    "population_size": summary["population_size"],
                    "coverage": summary["coverage"],
                    "exclusions": summary["exclusions"],
                    "outcomes": [
                        {
                            "program_outcome_id": item["program_outcome_id"],
                            "code": item["code"],
                            "label": item["label"],
                            "mean": item["mean"],
                            "median": item["median"],
                            "n": item["n"],
                            "population_size": item["population_size"],
                            "coverage": item["coverage"],
                            "exclusions": item["exclusions"],
                        }
                        for item in summary["outcomes"]
                    ],
                }
            )

        first = ordered[0]
        return {
            "program_id": str(first.program_id),
            "po_set_version": first.po_set_version,
            "points": points,
        }
