"""Offering and cumulative program outcome calculation service (CALC-02).

Implements two-phase capture -> compute -> persist:
1. Short atomic capture: lock Program and CourseOffering rows in deterministic PK order,
   freeze canonical JSON manifest, compute SHA-256 input_hash, return existing completed
   run if identical, otherwise create a pending CalculationRun and release locks.
2. Pure Decimal calculation outside any DB lock using `calc.kernel`.
3. Short atomic persist: bulk-create OutcomeScore rows and mark the run completed (or
   mark failed with zero partial scores on unexpected error).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from typing import Any

from access.policy import AuthorizationService
from calc.kernel import (
    CTX,
    KERNEL_VERSION,
    EntryState,
    ResultStatus,
    ScoreEntry,
    ScoreResult,
    canonical_decimal,
    compute_course_po,
    compute_cumulative_po,
    compute_lo,
    entry_from_result,
    exempt_entry,
    grade_entry,
)
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from wireup import injectable

from .. import policy, scoping
from ..models import (
    Assessment,
    CalculationRun,
    CourseOffering,
    Grade,
    GradeHistory,
    OutcomeScore,
    Program,
    ProgramOutcomeSet,
    Syllabus,
)

ENGINE_VERSION = KERNEL_VERSION
CALC_POLICY_VERSION = "calc-policy-v1"

_ZERO = Decimal(0)
_SCORE_QUANTUM = Decimal("0.000001")
_COVERAGE_QUANTUM = Decimal("0.0001")


def _quantize_score(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(_SCORE_QUANTUM, rounding=ROUND_HALF_EVEN, context=CTX)


def _quantize_coverage(scored_weight: Decimal, mapped_weight: Decimal) -> Decimal:
    if mapped_weight <= 0:
        return Decimal("0.0000")
    ratio = CTX.divide(scored_weight, mapped_weight)
    return ratio.quantize(_COVERAGE_QUANTUM, rounding=ROUND_HALF_UP, context=CTX)


def _numerator_denominator(result: ScoreResult) -> tuple[Decimal | None, Decimal | None]:
    if result.status is not ResultStatus.OK:
        return None, None
    numerator = _ZERO
    for contrib in result.contributions:
        numerator = CTX.add(numerator, CTX.multiply(contrib.weight, contrib.value))
    return _quantize_score(numerator), _quantize_score(result.total_weight)


def _match_gradebook_assessments(
    syllabus_assessments: list[Any],
    approved_assessments: list[Assessment],
) -> dict[str, str | None]:
    """Deterministically link SyllabusAssessment rows to approved gradebook Assessment rows."""
    by_exact: dict[str, list[Assessment]] = {}
    for asmt in approved_assessments:
        key = asmt.title.strip().casefold()
        by_exact.setdefault(key, []).append(asmt)

    linked: dict[str, str | None] = {}
    for sa in syllabus_assessments:
        code_key = sa.code.strip().casefold()
        exact_matches = by_exact.get(code_key, [])
        if exact_matches:
            linked[str(sa.pk)] = str(exact_matches[0].pk)
            continue

        prefix_matches = [
            a for a in approved_assessments if a.title.strip().casefold().startswith(code_key)
        ]
        if len(prefix_matches) == 1:
            linked[str(sa.pk)] = str(prefix_matches[0].pk)
        else:
            linked[str(sa.pk)] = None
    return linked


def _canonical_hash(manifest: dict[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class _OfferingComputation:
    score_rows: list[dict[str, Any]]
    course_po_by_enrollment: dict[str, dict[str, ScoreResult]]
    complete_by_enrollment: dict[str, bool]
    offering_complete: bool


def _compute_offering(
    offering_data: dict[str, Any],
    po_list: list[dict[str, Any]],
    po_set_version: int,
) -> _OfferingComputation:
    """Pure Decimal calculation for one offering from its frozen manifest snapshot."""
    offering_id = offering_data["id"]
    syllabus = offering_data["syllabus"]
    syllabus_is_official = (
        syllabus is not None
        and syllabus["status"] == Syllabus.Status.APPROVED
        and syllabus["po_set_version"] == po_set_version
    )

    sa_by_id = {sa["id"]: sa for sa in offering_data["syllabus_assessments"]}
    lo_list = offering_data["learning_outcomes"]
    lo_by_id = {lo["id"]: lo for lo in lo_list}

    # Index active Assessment -> LO mappings by LO id.
    a_lo_by_lo: dict[str, list[dict[str, Any]]] = {lo["id"]: [] for lo in lo_list}
    for mapping in offering_data["assessment_lo_mappings"]:
        sa = sa_by_id.get(mapping["assessment_id"])
        if (
            mapping["is_active"]
            and sa is not None
            and sa["is_active"]
            and Decimal(mapping["weight"]) > 0
            and mapping["learning_outcome_id"] in a_lo_by_lo
        ):
            a_lo_by_lo[mapping["learning_outcome_id"]].append(mapping)

    # Index active LO -> PO mappings by PO id.
    lo_po_by_po: dict[str, list[dict[str, Any]]] = {po["id"]: [] for po in po_list}
    for mapping in offering_data["lo_po_mappings"]:
        if (
            mapping["is_active"]
            and mapping["weight"] > 0
            and mapping["program_outcome_id"] in lo_po_by_po
            and mapping["learning_outcome_id"] in lo_by_id
        ):
            lo_po_by_po[mapping["program_outcome_id"]].append(mapping)

    # Index grades by (enrollment_id, gradebook_assessment_id).
    grades_by_key: dict[tuple[str, str], dict[str, Any]] = {
        (g["enrollment_id"], g["assessment_id"]): g for g in offering_data["grades"]
    }

    required_active_sas = [
        sa for sa in offering_data["syllabus_assessments"] if sa["is_active"] and sa["is_required"]
    ]
    eligible_enrollments = [
        enr for enr in offering_data["enrollments"] if enr["eligible_for_outcomes"]
    ]

    score_rows: list[dict[str, Any]] = []
    course_po_by_enrollment: dict[str, dict[str, ScoreResult]] = {}
    complete_by_enrollment: dict[str, bool] = {}

    for enr in eligible_enrollments:
        enr_id = enr["id"]
        student_id = enr["student_id"]

        # Check whether every required active syllabus assessment has a released non-missing grade.
        enr_required_released = syllabus_is_official
        if enr_required_released:
            for sa in required_active_sas:
                linked_id = sa["linked_assessment_id"]
                if linked_id is None:
                    enr_required_released = False
                    break
                grade = grades_by_key.get((enr_id, linked_id))
                if (
                    grade is None
                    or grade["batch_released_at"] is None
                    or grade["state"] not in (Grade.State.SCORED, Grade.State.EXEMPT)
                ):
                    enr_required_released = False
                    break

        lo_results: dict[str, ScoreResult] = {}
        enr_has_incomplete = False

        # --- Assessment -> LO ------------------------------------------------
        for lo in lo_list:
            lo_id = lo["id"]
            mappings = a_lo_by_lo[lo_id]
            entries: list[ScoreEntry] = []
            entry_meta: dict[str, dict[str, Any]] = {}
            mapped_weight = _ZERO

            for mapping in mappings:
                sa = sa_by_id[mapping["assessment_id"]]
                weight = Decimal(mapping["weight"])
                mapped_weight = CTX.add(mapped_weight, weight)
                entry_key = f"sa:{sa['id']}"
                linked_id = sa["linked_assessment_id"]
                grade = grades_by_key.get((enr_id, linked_id)) if linked_id else None

                if grade is not None and grade["state"] == Grade.State.SCORED:
                    entry = grade_entry(
                        entry_key, weight, grade["points_earned"], grade["points_possible"]
                    )
                elif grade is not None and grade["state"] == Grade.State.EXEMPT:
                    reason = (grade.get("reason") or "").strip() or "exempt"
                    entry = exempt_entry(entry_key, weight, reason)
                elif sa["is_required"]:
                    possible = grade["points_possible"] if grade is not None else sa["max_points"]
                    entry = grade_entry(entry_key, weight, None, possible)
                else:
                    entry = ScoreEntry(entry_key, weight, EntryState.NOT_ASSESSED)

                entries.append(entry)
                entry_meta[entry_key] = {
                    "mapping_id": mapping["id"],
                    "syllabus_assessment_id": sa["id"],
                    "assessment_code": sa["code"],
                    "assessment_id": linked_id,
                    "weight": canonical_decimal(weight),
                    "grade_id": grade["id"] if grade is not None else None,
                    "grade_version": grade["version"] if grade is not None else None,
                    "grade_state": grade["state"] if grade is not None else "missing",
                    "batch_id": grade["batch_id"] if grade is not None else None,
                    "batch_released_at": grade["batch_released_at"] if grade is not None else None,
                    "points_earned": grade["points_earned"] if grade is not None else None,
                    "points_possible": (
                        grade["points_possible"] if grade is not None else sa["max_points"]
                    ),
                }

            lo_result = compute_lo(entries)
            lo_results[lo_id] = lo_result
            if lo_result.status is ResultStatus.INCOMPLETE:
                enr_has_incomplete = True

            scored_weight = _ZERO
            for entry in entries:
                if entry.state is EntryState.SCORED:
                    scored_weight = CTX.add(scored_weight, entry.weight)

            numerator, denominator = _numerator_denominator(lo_result)
            contributions_evidence = []
            for contrib in lo_result.contributions:
                meta = dict(entry_meta[contrib.key])
                meta["normalized_score"] = canonical_decimal(contrib.value)
                contributions_evidence.append(meta)

            score_rows.append(
                {
                    "level": OutcomeScore.Level.LO,
                    "student_id": student_id,
                    "offering_id": offering_id,
                    "learning_outcome_id": lo_id,
                    "program_outcome_id": None,
                    "outcome_code": lo["code"],
                    "value": _quantize_score(lo_result.value),
                    "numerator": numerator,
                    "denominator": denominator,
                    "coverage": _quantize_coverage(scored_weight, mapped_weight),
                    "status": lo_result.status.value,
                    "evidence": {
                        "kernel_version": KERNEL_VERSION,
                        "display_value": lo_result.display(),
                        "exact_value": (
                            None if lo_result.value is None else canonical_decimal(lo_result.value)
                        ),
                        "enrollment_id": enr_id,
                        "syllabus_id": syllabus["id"] if syllabus else None,
                        "syllabus_version": syllabus["version"] if syllabus else None,
                        "contributions": contributions_evidence,
                        "missing": [entry_meta[k]["assessment_code"] for k in lo_result.missing],
                        "exemptions": [
                            {"assessment_code": entry_meta[k]["assessment_code"], "reason": r}
                            for k, r in lo_result.exemptions
                        ],
                    },
                }
            )

        # --- LO -> Course PO -------------------------------------------------
        enr_po_results: dict[str, ScoreResult] = {}
        for po in po_list:
            po_id = po["id"]
            mappings = lo_po_by_po[po_id]
            entries = []
            lo_meta: dict[str, dict[str, Any]] = {}
            mapped_weight = _ZERO

            for mapping in mappings:
                lo_id = mapping["learning_outcome_id"]
                lo = lo_by_id[lo_id]
                weight = Decimal(mapping["weight"])
                mapped_weight = CTX.add(mapped_weight, weight)
                entry_key = f"lo:{lo_id}"
                lo_res = lo_results[lo_id]
                entries.append(entry_from_result(entry_key, weight, lo_res))
                lo_meta[entry_key] = {
                    "mapping_id": mapping["id"],
                    "learning_outcome_id": lo_id,
                    "lo_code": lo["code"],
                    "lo_status": lo_res.status.value,
                    "lo_value": None if lo_res.value is None else canonical_decimal(lo_res.value),
                    "weight": canonical_decimal(weight),
                }

            if not entries:
                po_result = ScoreResult(ResultStatus.NOT_ASSESSED, None, _ZERO)
            else:
                po_result = compute_course_po(entries)
                if po_result.status is ResultStatus.UNMAPPED:
                    po_result = ScoreResult(
                        ResultStatus.NOT_ASSESSED,
                        None,
                        _ZERO,
                        exemptions=po_result.exemptions,
                    )

            enr_po_results[po_id] = po_result
            if po_result.status is ResultStatus.INCOMPLETE:
                enr_has_incomplete = True

            scored_weight = _ZERO
            for entry in entries:
                if entry.state is EntryState.SCORED:
                    scored_weight = CTX.add(scored_weight, entry.weight)

            numerator, denominator = _numerator_denominator(po_result)
            contributions_evidence = []
            for contrib in po_result.contributions:
                meta = dict(lo_meta[contrib.key])
                meta["value"] = canonical_decimal(contrib.value)
                contributions_evidence.append(meta)

            score_rows.append(
                {
                    "level": OutcomeScore.Level.COURSE_PO,
                    "student_id": student_id,
                    "offering_id": offering_id,
                    "learning_outcome_id": None,
                    "program_outcome_id": po_id,
                    "outcome_code": po["code"],
                    "value": _quantize_score(po_result.value),
                    "numerator": numerator,
                    "denominator": denominator,
                    "coverage": _quantize_coverage(scored_weight, mapped_weight),
                    "status": po_result.status.value,
                    "evidence": {
                        "kernel_version": KERNEL_VERSION,
                        "display_value": po_result.display(),
                        "exact_value": (
                            None if po_result.value is None else canonical_decimal(po_result.value)
                        ),
                        "enrollment_id": enr_id,
                        "syllabus_id": syllabus["id"] if syllabus else None,
                        "syllabus_version": syllabus["version"] if syllabus else None,
                        "contributions": contributions_evidence,
                        "missing": [lo_meta[k]["lo_code"] for k in po_result.missing],
                        "exemptions": [
                            {"lo_code": lo_meta[k]["lo_code"], "reason": r}
                            for k, r in po_result.exemptions
                        ],
                    },
                }
            )

        course_po_by_enrollment[enr_id] = enr_po_results
        complete_by_enrollment[enr_id] = enr_required_released and not enr_has_incomplete

    offering_complete = (
        syllabus_is_official and bool(eligible_enrollments) and all(complete_by_enrollment.values())
    )
    return _OfferingComputation(
        score_rows=score_rows,
        course_po_by_enrollment=course_po_by_enrollment,
        complete_by_enrollment=complete_by_enrollment,
        offering_complete=offering_complete,
    )


def _compute_from_manifest(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """Pure Decimal computation for offering or program scope from frozen manifest."""
    scope_kind = manifest["scope_kind"]
    po_set_version = manifest["po_set"]["version"]
    po_list = manifest["po_set"]["outcomes"]

    if scope_kind == CalculationRun.ScopeKind.OFFERING:
        offering_data = manifest["offerings"][0]
        result = _compute_offering(offering_data, po_list, po_set_version)
        return result.score_rows, result.offering_complete

    # --- Program (cumulative PO) scope --------------------------------------
    # Policy calc-policy-v1: latest completed approved attempt per catalog course.
    offering_results: dict[str, _OfferingComputation] = {}
    offering_by_id: dict[str, dict[str, Any]] = {}
    course_po_rows_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    lo_rows_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    attempts_by_student_course: dict[
        tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]
    ] = {}

    for offering_data in manifest["offerings"]:
        off_id = offering_data["id"]
        offering_by_id[off_id] = offering_data
        off_comp = _compute_offering(offering_data, po_list, po_set_version)
        offering_results[off_id] = off_comp
        for row in off_comp.score_rows:
            enr_id = row["evidence"]["enrollment_id"]
            if row["level"] == OutcomeScore.Level.COURSE_PO and row["program_outcome_id"]:
                course_po_rows_by_key[(off_id, enr_id, row["program_outcome_id"])] = row
            elif row["level"] == OutcomeScore.Level.LO and row["learning_outcome_id"]:
                lo_rows_by_key[(off_id, enr_id, row["learning_outcome_id"])] = row
        for enr in offering_data["enrollments"]:
            if not enr["eligible_for_outcomes"]:
                continue
            key = (enr["student_id"], offering_data["course_id"])
            attempts_by_student_course.setdefault(key, []).append((offering_data, enr))

    # Select latest completed approved attempt per (student, catalog course).
    selected_by_student: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for (student_id, _course_id), candidates in sorted(attempts_by_student_course.items()):
        chosen_offering, chosen_enr = max(
            candidates,
            key=lambda pair: (
                1 if pair[1]["status"] == "completed" else 0,
                pair[1]["attempt_number"],
                pair[0]["term_starts_at"],
                pair[0]["term_year"],
                pair[0]["id"],
                pair[1]["id"],
            ),
        )
        selected_by_student.setdefault(student_id, []).append((chosen_offering, chosen_enr))

    score_rows: list[dict[str, Any]] = []
    any_incomplete = False
    all_selected_complete = bool(selected_by_student)

    for student_id in sorted(selected_by_student.keys()):
        selected_attempts = sorted(
            selected_by_student[student_id],
            key=lambda pair: (pair[0]["course_code"], pair[0]["id"]),
        )
        for chosen_offering, chosen_enr in selected_attempts:
            if not offering_results[chosen_offering["id"]].complete_by_enrollment.get(
                chosen_enr["id"], False
            ):
                all_selected_complete = False

        for po in po_list:
            po_id = po["id"]
            entries: list[ScoreEntry] = []
            course_meta: dict[str, dict[str, Any]] = {}
            mapped_weight = _ZERO

            for chosen_offering, chosen_enr in selected_attempts:
                off_id = chosen_offering["id"]
                contrib = next(
                    (
                        c
                        for c in chosen_offering["course_po_contributions"]
                        if c["program_outcome_id"] == po_id
                    ),
                    None,
                )
                if contrib is None:
                    continue

                weight = Decimal(contrib["weight"])
                mapped_weight = CTX.add(mapped_weight, weight)
                course_po_res = offering_results[off_id].course_po_by_enrollment[chosen_enr["id"]][
                    po_id
                ]
                course_po_row = course_po_rows_by_key.get((off_id, chosen_enr["id"], po_id))
                lo_contributions: list[dict[str, Any]] = []
                if course_po_row is not None:
                    for lo_contrib in course_po_row["evidence"].get("contributions", []):
                        lo_id = lo_contrib["learning_outcome_id"]
                        lo_row = lo_rows_by_key.get((off_id, chosen_enr["id"], lo_id))
                        lo_evidence = lo_row["evidence"] if lo_row is not None else {}
                        lo_contributions.append(
                            {
                                **lo_contrib,
                                "numerator": (
                                    None
                                    if lo_row is None or lo_row["numerator"] is None
                                    else canonical_decimal(lo_row["numerator"])
                                ),
                                "denominator": (
                                    None
                                    if lo_row is None or lo_row["denominator"] is None
                                    else canonical_decimal(lo_row["denominator"])
                                ),
                                "assessment_contributions": list(
                                    lo_evidence.get("contributions", [])
                                ),
                                "missing": list(lo_evidence.get("missing", [])),
                                "exemptions": list(lo_evidence.get("exemptions", [])),
                            }
                        )

                entry_key = f"course:{chosen_offering['course_id']}"
                entries.append(entry_from_result(entry_key, weight, course_po_res))
                course_meta[entry_key] = {
                    "course_id": chosen_offering["course_id"],
                    "course_code": chosen_offering["course_code"],
                    "offering_id": off_id,
                    "term": f"{chosen_offering['term_year']}-{chosen_offering['term_season']}",
                    "syllabus_id": chosen_offering["syllabus"]["id"],
                    "syllabus_version": chosen_offering["syllabus"]["version"],
                    "enrollment_id": chosen_enr["id"],
                    "enrollment_status": chosen_enr["status"],
                    "attempt_number": chosen_enr["attempt_number"],
                    "contribution_id": contrib["id"],
                    "weight": canonical_decimal(weight),
                    "course_po_status": course_po_res.status.value,
                    "course_po_value": (
                        None
                        if course_po_res.value is None
                        else canonical_decimal(course_po_res.value)
                    ),
                    "lo_contributions": lo_contributions,
                }

            if not entries:
                cum_result = ScoreResult(ResultStatus.NOT_ASSESSED, None, _ZERO)
            else:
                cum_result = compute_cumulative_po(entries)
                if cum_result.status is ResultStatus.UNMAPPED:
                    cum_result = ScoreResult(
                        ResultStatus.NOT_ASSESSED,
                        None,
                        _ZERO,
                        exemptions=cum_result.exemptions,
                    )

            if cum_result.status is ResultStatus.INCOMPLETE:
                any_incomplete = True

            scored_weight = _ZERO
            for entry in entries:
                if entry.state is EntryState.SCORED:
                    scored_weight = CTX.add(scored_weight, entry.weight)

            numerator, denominator = _numerator_denominator(cum_result)
            contributions_evidence = []
            for contrib_item in cum_result.contributions:
                meta = dict(course_meta[contrib_item.key])
                meta["value"] = canonical_decimal(contrib_item.value)
                contributions_evidence.append(meta)

            score_rows.append(
                {
                    "level": OutcomeScore.Level.CUMULATIVE_PO,
                    "student_id": student_id,
                    "offering_id": None,
                    "learning_outcome_id": None,
                    "program_outcome_id": po_id,
                    "outcome_code": po["code"],
                    "value": _quantize_score(cum_result.value),
                    "numerator": numerator,
                    "denominator": denominator,
                    "coverage": _quantize_coverage(scored_weight, mapped_weight),
                    "status": cum_result.status.value,
                    "evidence": {
                        "kernel_version": KERNEL_VERSION,
                        "policy_version": CALC_POLICY_VERSION,
                        "display_value": cum_result.display(),
                        "exact_value": (
                            None
                            if cum_result.value is None
                            else canonical_decimal(cum_result.value)
                        ),
                        "contributions": contributions_evidence,
                        "missing": [course_meta[k]["course_code"] for k in cum_result.missing],
                        "exemptions": [
                            {"course_code": course_meta[k]["course_code"], "reason": r}
                            for k, r in cum_result.exemptions
                        ],
                    },
                }
            )

    program_complete = all_selected_complete and not any_incomplete
    return score_rows, program_complete


@injectable
class CalculationService:
    """Orchestrates deterministic offering and cumulative program outcome calculations."""

    model = CalculationRun

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(CalculationRun.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("-created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = CalculationRun.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return scoping.scope_calculation_runs(effective_actor, queryset).select_related(
            "program", "offering", "created_by"
        )

    def list_scores(self, *, run: CalculationRun, **filters):
        qs = run.scores.select_related("student", "offering", "learning_outcome", "program_outcome")
        allowed = {
            "level",
            "student",
            "student_id",
            "offering",
            "offering_id",
            "outcome_code",
            "status",
        }
        clean = {k: v for k, v in filters.items() if k in allowed and v not in (None, "")}
        if clean:
            qs = qs.filter(**clean)
        return qs.order_by("level", "student_id", "outcome_code", "id")

    # -- Manifest capture (reusable by CALC-03) ------------------------------

    def build_manifest_and_hash(
        self,
        *,
        scope_kind: str,
        program: Program,
        offering: CourseOffering | None = None,
        lock: bool = False,
    ) -> tuple[dict[str, Any], str, int]:
        """Capture canonical JSON manifest and SHA-256 input hash.

        When `lock=True`, callers must invoke this inside `@transaction.atomic`;
        it locks Program and CourseOffering rows in deterministic PK order.
        """
        if scope_kind not in (
            CalculationRun.ScopeKind.OFFERING,
            CalculationRun.ScopeKind.PROGRAM,
        ):
            raise ValidationError({"scope_kind": "Invalid calculation scope kind."})

        if scope_kind == CalculationRun.ScopeKind.OFFERING:
            if offering is None:
                raise ValidationError({"offering": "An offering is required for offering runs."})
            if offering.program_id != program.pk:
                raise ValidationError({"offering": "Offering does not belong to the program."})
        elif offering is not None:
            raise ValidationError({"offering": "Program runs must not specify an offering."})

        # Lock Program then CourseOffering rows in deterministic PK order.
        if lock:
            program = Program.objects.select_for_update().get(pk=program.pk)
        else:
            program = Program.objects.get(pk=program.pk)

        active_set = (
            ProgramOutcomeSet.objects.filter(
                program_id=program.pk,
                status=ProgramOutcomeSet.Status.ACTIVE,
                effective_date__lte=timezone.localdate(),
            )
            .order_by("-effective_date")
            .first()
        )
        if active_set is None:
            raise ValidationError("No active PO-set exists for this program.")

        po_outcomes = list(active_set.outcomes.order_by("ordering", "id"))

        if scope_kind == CalculationRun.ScopeKind.OFFERING:
            assert offering is not None
            offering_qs = CourseOffering.objects.select_related("course", "term").filter(
                pk=offering.pk
            )
            if lock:
                offering_qs = offering_qs.select_for_update(of=("self",))
            locked_offerings = list(offering_qs.order_by("pk"))
            offering_syllabus_pairs = [
                (off, self._select_offering_syllabus(off, active_set.version))
                for off in locked_offerings
            ]
        else:
            eligible_offering_ids = list(
                Syllabus.objects.filter(
                    offering__program_id=program.pk,
                    status=Syllabus.Status.APPROVED,
                    po_set_version=active_set.version,
                )
                .values_list("offering_id", flat=True)
                .distinct()
            )
            offering_qs = CourseOffering.objects.select_related("course", "term").filter(
                pk__in=eligible_offering_ids
            )
            if lock:
                offering_qs = offering_qs.select_for_update(of=("self",))
            locked_offerings = list(offering_qs.order_by("pk"))
            offering_syllabus_pairs = []
            for off in locked_offerings:
                syl = off.syllabi.filter(
                    status=Syllabus.Status.APPROVED,
                    po_set_version=active_set.version,
                ).first()
                if syl is not None:
                    offering_syllabus_pairs.append((off, syl))

        offerings_manifest = [
            self._capture_offering_manifest(off, syl) for off, syl in offering_syllabus_pairs
        ]

        manifest: dict[str, Any] = {
            "scope_kind": scope_kind,
            "engine_version": ENGINE_VERSION,
            "policy_version": CALC_POLICY_VERSION,
            "eligibility_policy_version": policy.POLICY_VERSION,
            "program": {
                "id": str(program.pk),
                "code": program.code,
                "input_revision": program.input_revision,
            },
            "po_set": {
                "id": str(active_set.pk),
                "version": active_set.version,
                "outcomes": [
                    {
                        "id": str(po.pk),
                        "code": po.code,
                        "ordering": po.ordering,
                    }
                    for po in po_outcomes
                ],
            },
            "offerings": offerings_manifest,
        }
        return manifest, _canonical_hash(manifest), active_set.version

    @staticmethod
    def _select_offering_syllabus(offering: CourseOffering, active_po_set_version: int) -> Syllabus:
        """Prefer approved syllabus bound to active PO-set; allow draft preview fallback."""
        official = offering.syllabi.filter(
            status=Syllabus.Status.APPROVED,
            po_set_version=active_po_set_version,
        ).first()
        if official is not None:
            return official

        draft = (
            offering.syllabi.filter(
                status=Syllabus.Status.DRAFT,
                po_set_version=active_po_set_version,
            ).first()
            or offering.syllabi.filter(status=Syllabus.Status.DRAFT).order_by("-version").first()
        )
        if draft is not None:
            return draft

        raise ValidationError("No syllabus exists for this offering.")

    @staticmethod
    def _capture_offering_manifest(offering: CourseOffering, syllabus: Syllabus) -> dict[str, Any]:
        learning_outcomes = list(syllabus.learning_outcomes.order_by("order", "id"))
        syllabus_assessments = list(syllabus.assessments.order_by("order", "id"))
        approved_assessments = list(
            Assessment.objects.filter(
                offering_id=offering.pk, status=Assessment.Status.APPROVED
            ).order_by("created_at", "id")
        )
        linked_map = _match_gradebook_assessments(syllabus_assessments, approved_assessments)

        a_lo_mappings = list(
            syllabus.assessment_lo_mappings.order_by("assessment_id", "learning_outcome_id", "id")
        )
        lo_po_mappings = list(
            syllabus.lo_po_mappings.order_by("learning_outcome_id", "program_outcome_id", "id")
        )
        po_contributions = list(syllabus.po_contributions.order_by("program_outcome_id", "id"))

        enrollments = list(offering.enrollments.order_by("student_id", "id"))
        grades = list(
            Grade.objects.filter(offering_id=offering.pk)
            .select_related("batch")
            .order_by("enrollment_id", "assessment_id", "id")
        )

        # Capture latest history reason for each grade version (needed for EXEMPT reasons).
        grade_ids = [g.pk for g in grades]
        reason_by_grade_version: dict[tuple[Any, int], str] = {}
        if grade_ids:
            for hist in GradeHistory.objects.filter(grade_id__in=grade_ids).values(
                "grade_id", "version", "reason"
            ):
                reason_by_grade_version[(hist["grade_id"], hist["version"])] = hist["reason"]

        return {
            "id": str(offering.pk),
            "course_id": str(offering.course_id),
            "course_code": offering.course.code,
            "term_id": str(offering.term_id),
            "term_year": offering.term.year,
            "term_season": offering.term.season,
            "term_starts_at": offering.term.starts_at.isoformat(),
            "section": offering.section,
            "status": offering.status,
            "input_revision": offering.input_revision,
            "syllabus": {
                "id": str(syllabus.pk),
                "version": syllabus.version,
                "status": syllabus.status,
                "po_set_version": syllabus.po_set_version,
                "mapping_revision": syllabus.mapping_revision,
                "approved_at": syllabus.approved_at.isoformat() if syllabus.approved_at else None,
            },
            "learning_outcomes": [
                {"id": str(lo.pk), "code": lo.code, "order": lo.order} for lo in learning_outcomes
            ],
            "syllabus_assessments": [
                {
                    "id": str(sa.pk),
                    "code": sa.code,
                    "kind": sa.kind,
                    "order": sa.order,
                    "is_required": sa.is_required,
                    "is_active": sa.is_active,
                    "max_points": canonical_decimal(sa.max_points),
                    "linked_assessment_id": linked_map[str(sa.pk)],
                }
                for sa in syllabus_assessments
            ],
            "assessment_lo_mappings": [
                {
                    "id": str(m.pk),
                    "assessment_id": str(m.assessment_id),
                    "learning_outcome_id": str(m.learning_outcome_id),
                    "weight": canonical_decimal(m.weight),
                    "is_active": m.is_active,
                }
                for m in a_lo_mappings
            ],
            "lo_po_mappings": [
                {
                    "id": str(m.pk),
                    "learning_outcome_id": str(m.learning_outcome_id),
                    "program_outcome_id": str(m.program_outcome_id),
                    "weight": m.weight,
                    "is_active": m.is_active,
                }
                for m in lo_po_mappings
            ],
            "course_po_contributions": [
                {
                    "id": str(c.pk),
                    "program_outcome_id": str(c.program_outcome_id),
                    "weight": c.weight,
                }
                for c in po_contributions
            ],
            "enrollments": [
                {
                    "id": str(enr.pk),
                    "student_id": enr.student_id,
                    "status": enr.status,
                    "attempt_number": enr.attempt_number,
                    "eligible_for_outcomes": enr.eligible_for_outcomes,
                    "eligibility_policy_version": enr.eligibility_policy_version,
                }
                for enr in enrollments
            ],
            "grades": [
                {
                    "id": str(g.pk),
                    "enrollment_id": str(g.enrollment_id),
                    "assessment_id": str(g.assessment_id),
                    "batch_id": str(g.batch_id),
                    "batch_released_at": (
                        g.batch.released_at.isoformat() if g.batch.released_at else None
                    ),
                    "state": g.state,
                    "points_earned": (
                        None if g.points_earned is None else canonical_decimal(g.points_earned)
                    ),
                    "points_possible": canonical_decimal(g.points_possible),
                    "version": g.version,
                    "reason": reason_by_grade_version.get((g.pk, g.version), ""),
                }
                for g in grades
            ],
        }

    # -- Two-phase capture -> compute -> persist -----------------------------

    def run_offering(
        self, *, offering: CourseOffering, actor: Any = None
    ) -> tuple[CalculationRun, bool]:
        """Run (or replay) an offering calculation. Returns (run, created)."""
        effective_actor = actor if actor is not None else self.actor
        return self._execute_run(
            scope_kind=CalculationRun.ScopeKind.OFFERING,
            program=offering.program,
            offering=offering,
            actor=effective_actor,
        )

    def run_program(self, *, program: Program, actor: Any = None) -> tuple[CalculationRun, bool]:
        """Run (or replay) a cumulative program calculation. Returns (run, created)."""
        effective_actor = actor if actor is not None else self.actor
        return self._execute_run(
            scope_kind=CalculationRun.ScopeKind.PROGRAM,
            program=program,
            offering=None,
            actor=effective_actor,
        )

    def _execute_run(
        self,
        *,
        scope_kind: str,
        program: Program,
        offering: CourseOffering | None,
        actor: Any,
    ) -> tuple[CalculationRun, bool]:
        # Phase 1: short atomic capture under deterministic row locks.
        run, existing = self._capture_pending_run(
            scope_kind=scope_kind,
            program=program,
            offering=offering,
            actor=actor,
        )
        if existing is not None:
            return existing, False
        assert run is not None

        # Phase 2: pure Decimal calculation outside any DB lock/transaction.
        try:
            score_dicts, is_complete = _compute_from_manifest(run.manifest)
        except Exception as exc:
            self._mark_failed(run=run, error_detail=str(exc))
            raise

        # Phase 3: short atomic persist of OutcomeScore rows + completed transition.
        return self._persist_completed_run(
            run=run,
            score_dicts=score_dicts,
            is_complete=is_complete,
        )

    @transaction.atomic
    def _capture_pending_run(
        self,
        *,
        scope_kind: str,
        program: Program,
        offering: CourseOffering | None,
        actor: Any,
    ) -> tuple[CalculationRun | None, CalculationRun | None]:
        manifest, input_hash, po_set_version = self.build_manifest_and_hash(
            scope_kind=scope_kind,
            program=program,
            offering=offering,
            lock=True,
        )

        existing = self._find_completed_run(
            scope_kind=scope_kind,
            program_id=program.pk,
            offering_id=offering.pk if offering is not None else None,
            input_hash=input_hash,
        )
        if existing is not None:
            return None, existing

        run = CalculationRun.objects.create(
            scope_kind=scope_kind,
            program_id=program.pk,
            offering_id=offering.pk if offering is not None else None,
            po_set_version=po_set_version,
            engine_version=ENGINE_VERSION,
            policy_version=CALC_POLICY_VERSION,
            input_hash=input_hash,
            manifest=manifest,
            status=CalculationRun.Status.PENDING,
            is_complete_for_publication=False,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        return run, None

    def _persist_completed_run(
        self,
        *,
        run: CalculationRun,
        score_dicts: list[dict[str, Any]],
        is_complete: bool,
    ) -> tuple[CalculationRun, bool]:
        try:
            with transaction.atomic():
                score_objects = [
                    OutcomeScore(
                        run=run,
                        level=row["level"],
                        student_id=row["student_id"],
                        offering_id=row["offering_id"],
                        learning_outcome_id=row["learning_outcome_id"],
                        program_outcome_id=row["program_outcome_id"],
                        outcome_code=row["outcome_code"],
                        value=row["value"],
                        numerator=row["numerator"],
                        denominator=row["denominator"],
                        coverage=row["coverage"],
                        status=row["status"],
                        evidence=row["evidence"],
                    )
                    for row in score_dicts
                ]
                if score_objects:
                    OutcomeScore.objects.bulk_create(score_objects)
                run.status = CalculationRun.Status.COMPLETED
                run.is_complete_for_publication = is_complete
                run.completed_at = timezone.now()
                run.save(
                    update_fields=[
                        "status",
                        "is_complete_for_publication",
                        "completed_at",
                        "updated_at",
                    ]
                )
            return run, True
        except IntegrityError:
            existing = self._find_completed_run(
                scope_kind=run.scope_kind,
                program_id=run.program_id,
                offering_id=run.offering_id,
                input_hash=run.input_hash,
            )
            self._mark_failed(
                run=run, error_detail="Superseded by concurrent identical completed run."
            )
            if existing is not None:
                return existing, False
            raise
        except Exception as exc:
            self._mark_failed(run=run, error_detail=str(exc))
            raise

    @staticmethod
    def _find_completed_run(
        *, scope_kind: str, program_id: Any, offering_id: Any, input_hash: str
    ) -> CalculationRun | None:
        filters: dict[str, Any] = {
            "scope_kind": scope_kind,
            "program_id": program_id,
            "input_hash": input_hash,
            "engine_version": ENGINE_VERSION,
            "policy_version": CALC_POLICY_VERSION,
            "status": CalculationRun.Status.COMPLETED,
        }
        if scope_kind == CalculationRun.ScopeKind.OFFERING:
            filters["offering_id"] = offering_id
        else:
            filters["offering__isnull"] = True
        return CalculationRun.objects.filter(**filters).first()

    @staticmethod
    @transaction.atomic
    def _mark_failed(*, run: CalculationRun, error_detail: str) -> None:
        CalculationRun.objects.filter(pk=run.pk).update(
            status=CalculationRun.Status.FAILED,
            is_complete_for_publication=False,
            error_detail=error_detail,
            updated_at=timezone.now(),
        )
        run.status = CalculationRun.Status.FAILED
        run.is_complete_for_publication = False
        run.error_detail = error_detail
