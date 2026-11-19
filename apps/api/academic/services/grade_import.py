"""CSV grade import validation (dry-run) and atomic idempotent apply."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from access.models import AuditEvent, Scope
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from wireup import injectable

from ..models import (
    Assessment,
    CourseOffering,
    Enrollment,
    Grade,
    GradeBatch,
    GradeHistory,
    GradeImportRecord,
    ProgramMembership,
)
from .revisions import RevisionTracker

MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB UTF-8 byte limit
MAX_CSV_ROWS = 10_000  # 10,000 data rows maximum
REQUIRED_COLUMNS = ("student_identifier", "assessment", "state", "points_earned")
OPTIONAL_COLUMNS = ("reason",)
ALL_COLUMNS = (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS)
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")


def sanitize_filename(filename: str) -> str:
    """Strip directory paths, control chars, and unsafe characters; clamp to 120 chars."""
    if not filename:
        return "grades.csv"
    base = os.path.basename(filename.replace("\\", "/"))
    cleaned = _CONTROL_CHARS.sub("", base)
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", cleaned)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return "grades.csv"
    if len(cleaned) > 120:
        stem, ext = os.path.splitext(cleaned)
        ext = ext[:16]
        cleaned = f"{stem[: 120 - len(ext)]}{ext}"
    return cleaned


def escape_csv_formula(cell: str) -> str:
    """Prefix spreadsheet formula triggers with a single quote to neutralize injection."""
    if cell and cell[0] in FORMULA_PREFIXES:
        return f"'{cell}"
    return cell


def _normalize_csv_text(csv_text: str) -> str:
    csv_text = csv_text.removeprefix("\ufeff")
    return csv_text.replace("\r\n", "\n").replace("\r", "\n")


def compute_csv_checksum(csv_text: str) -> str:
    """Return deterministic SHA-256 hex digest of normalized UTF-8 CSV content."""
    normalized = _normalize_csv_text(csv_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class GradeImportConflict(Exception):
    """Raised when an import collides with an idempotency key or stale revision (HTTP 409)."""

    def __init__(self, *, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@injectable
class GradeImportService:
    """Validates and atomically applies CSV grade imports for a course offering."""

    def __init__(self, *, actor: Any = None):
        self.actor = actor

    def template_payload(self, *, offering: CourseOffering) -> dict[str, Any]:
        """Return CSV import limits, required columns, and a formula-safe sample CSV."""
        enrollment = (
            Enrollment.objects.filter(offering=offering, status=Enrollment.Status.ENROLLED)
            .select_related("student")
            .order_by("created_at", "id")
            .first()
        )
        assessment = (
            Assessment.objects.filter(offering=offering, status=Assessment.Status.APPROVED)
            .order_by("created_at", "id")
            .first()
        )

        student_id = "student-001"
        if enrollment is not None:
            membership = ProgramMembership.objects.filter(
                program_id=offering.program_id,
                user_id=enrollment.student_id,
                status=ProgramMembership.Status.ACTIVE,
            ).first()
            student_id = membership.student_number if membership else enrollment.student.username

        assessment_label = assessment.title if assessment is not None else "Midterm Exam"
        sample_points = "85.00"
        if assessment is not None and assessment.points_possible < Decimal("85.00"):
            sample_points = str(assessment.points_possible)

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(list(ALL_COLUMNS))
        writer.writerow(
            [
                escape_csv_formula(student_id),
                escape_csv_formula(assessment_label),
                escape_csv_formula(Grade.State.SCORED),
                escape_csv_formula(sample_points),
                escape_csv_formula(""),
            ]
        )

        return {
            "offering_id": str(offering.pk),
            "columns": list(ALL_COLUMNS),
            "required_columns": list(REQUIRED_COLUMNS),
            "max_bytes": MAX_CSV_BYTES,
            "max_rows": MAX_CSV_ROWS,
            "sample_csv": output.getvalue(),
        }

    def dry_run(
        self,
        *,
        offering: CourseOffering,
        csv_text: str,
        batch: GradeBatch | None = None,
        batch_name: str = "",
        filename: str = "",
    ) -> dict[str, Any]:
        """Validate a grade CSV without writing any database records."""
        if not isinstance(csv_text, str):
            raise ValidationError({"csv_text": "CSV content must be a UTF-8 string."})

        raw_bytes = csv_text.encode("utf-8")
        if len(raw_bytes) > MAX_CSV_BYTES:
            raise ValidationError(
                {"csv_text": (f"CSV exceeds maximum size of {MAX_CSV_BYTES} bytes (5 MB).")}
            )

        normalized = _normalize_csv_text(csv_text)
        if not normalized.strip():
            raise ValidationError({"csv_text": "CSV content cannot be empty."})

        if batch is not None and batch.offering_id != offering.pk:
            raise ValidationError({"batch": "This batch belongs to a different offering."})

        resolved_batch = batch
        if resolved_batch is None and batch_name.strip():
            resolved_batch = GradeBatch.objects.filter(
                offering=offering, name=batch_name.strip()
            ).first()
        target_batch_released = (
            resolved_batch is not None and resolved_batch.released_at is not None
        )

        reader = csv.reader(io.StringIO(normalized))
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValidationError({"csv_text": "CSV content cannot be empty."}) from exc

        headers = [col.strip() for col in raw_header]
        if not headers or all(not h for h in headers):
            raise ValidationError({"csv_text": "CSV header row cannot be empty."})

        seen_headers: set[str] = set()
        duplicate_headers: list[str] = []
        for col in headers:
            if col in seen_headers:
                duplicate_headers.append(col)
            seen_headers.add(col)
        if duplicate_headers:
            raise ValidationError(
                {
                    "csv_text": (
                        f"Duplicate CSV header columns: {', '.join(sorted(set(duplicate_headers)))}."
                    )
                }
            )

        unknown_headers = [col for col in headers if col not in ALL_COLUMNS]
        if unknown_headers:
            raise ValidationError(
                {
                    "csv_text": (
                        f"Unknown CSV header columns: {', '.join(unknown_headers)}. "
                        f"Allowed columns: {', '.join(ALL_COLUMNS)}."
                    )
                }
            )

        missing_headers = [col for col in REQUIRED_COLUMNS if col not in seen_headers]
        if missing_headers:
            raise ValidationError(
                {"csv_text": (f"Missing required CSV columns: {', '.join(missing_headers)}.")}
            )

        data_rows: list[list[str]] = []
        for raw_row in reader:
            if not any(cell.strip() for cell in raw_row):
                continue
            data_rows.append(raw_row)
            if len(data_rows) > MAX_CSV_ROWS:
                raise ValidationError(
                    {"csv_text": (f"CSV exceeds maximum row limit of {MAX_CSV_ROWS} rows.")}
                )

        if not data_rows:
            raise ValidationError({"csv_text": "CSV must contain at least one data row."})

        # Preload offering enrollments, active program memberships, assessments, and existing grades.
        enrollments = list(Enrollment.objects.filter(offering=offering).select_related("student"))
        enrollment_by_id: dict[str, Enrollment] = {str(e.pk): e for e in enrollments}
        enrollment_by_username: dict[str, Enrollment] = {e.student.username: e for e in enrollments}
        enrollment_by_student_id: dict[Any, Enrollment] = {e.student_id: e for e in enrollments}
        enrollment_by_student_number: dict[str, Enrollment] = {}
        for membership in ProgramMembership.objects.filter(
            program_id=offering.program_id,
            status=ProgramMembership.Status.ACTIVE,
        ).only("user_id", "student_number"):
            enr = enrollment_by_student_id.get(membership.user_id)
            if enr is not None:
                enrollment_by_student_number[membership.student_number] = enr

        assessments = list(Assessment.objects.filter(offering=offering))
        assessment_by_id: dict[str, Assessment] = {str(a.pk): a for a in assessments}
        assessments_by_title: dict[str, list[Assessment]] = {}
        for asmt in assessments:
            assessments_by_title.setdefault(asmt.title, []).append(asmt)

        existing_grades: dict[tuple[Any, Any], Grade] = {
            (g.enrollment_id, g.assessment_id): g
            for g in Grade.objects.filter(offering=offering).select_related("batch")
        }

        col_index = {name: idx for idx, name in enumerate(headers)}
        valid_states = list(Grade.State.values)
        valid_state_set = set(valid_states)

        seen_pairs: set[tuple[Any, Any]] = set()
        all_errors: list[dict[str, Any]] = []
        preview_rows: list[dict[str, Any]] = []
        valid_rows = 0
        invalid_rows = 0
        create_count = 0
        update_count = 0
        unchanged_count = 0

        for row_number, raw_row in enumerate(data_rows, start=1):
            row_errors: list[dict[str, Any]] = []

            def add_error(
                column: str,
                code: str,
                message: str,
                *,
                _row_number: int = row_number,
                _row_errors: list[dict[str, Any]] = row_errors,
            ) -> None:
                _row_errors.append(
                    {
                        "row_number": _row_number,
                        "column": column,
                        "code": code,
                        "message": message,
                    }
                )

            if len(raw_row) > len(headers):
                extra = [cell.strip() for cell in raw_row[len(headers) :] if cell.strip()]
                if extra:
                    add_error(
                        "row",
                        "extra_columns",
                        f"Row has {len(raw_row)} columns; expected {len(headers)}.",
                    )

            def cell_value(col_name: str, _raw_row: list[str] = raw_row) -> str:
                idx = col_index.get(col_name)
                if idx is None or idx >= len(_raw_row):
                    return ""
                return _raw_row[idx].strip()

            student_identifier = cell_value("student_identifier")
            assessment_identifier = cell_value("assessment")
            state_raw = cell_value("state")
            points_raw = cell_value("points_earned")
            reason = cell_value("reason")

            # 1. Resolve student enrollment in this offering
            enrollment: Enrollment | None = None
            if not student_identifier:
                add_error("student_identifier", "required", "Student identifier is required.")
            else:
                enrollment = (
                    enrollment_by_id.get(student_identifier)
                    or enrollment_by_student_number.get(student_identifier)
                    or enrollment_by_username.get(student_identifier)
                )
                if enrollment is None:
                    add_error(
                        "student_identifier",
                        "not_found",
                        f"Student '{student_identifier}' is not enrolled in this offering.",
                    )
                elif enrollment.status != Enrollment.Status.ENROLLED:
                    add_error(
                        "student_identifier",
                        "inactive_enrollment",
                        f"Enrollment for '{student_identifier}' is not active (status: {enrollment.status}).",
                    )

            # 2. Resolve approved assessment in this offering
            assessment: Assessment | None = None
            if not assessment_identifier:
                add_error("assessment", "required", "Assessment identifier is required.")
            else:
                assessment = assessment_by_id.get(assessment_identifier)
                if assessment is None:
                    matches = assessments_by_title.get(assessment_identifier, [])
                    if len(matches) == 1:
                        assessment = matches[0]
                    elif len(matches) > 1:
                        add_error(
                            "assessment",
                            "ambiguous",
                            f"Assessment title '{assessment_identifier}' is ambiguous; use the assessment UUID.",
                        )
                    else:
                        add_error(
                            "assessment",
                            "not_found",
                            f"Assessment '{assessment_identifier}' was not found in this offering.",
                        )
                if assessment is not None and assessment.status != Assessment.Status.APPROVED:
                    add_error(
                        "assessment",
                        "unapproved",
                        f"Assessment '{assessment.title}' is not approved.",
                    )

            # 3. Duplicate (enrollment, assessment) pair within the CSV
            if enrollment is not None and assessment is not None:
                pair = (enrollment.pk, assessment.pk)
                if pair in seen_pairs:
                    add_error(
                        "assessment",
                        "duplicate_row",
                        f"Duplicate entry for student '{student_identifier}' and assessment '{assessment.title}'.",
                    )
                else:
                    seen_pairs.add(pair)

            # 4. Validate grade state
            state = state_raw.lower()
            if not state:
                add_error("state", "required", "Grade state is required.")
            elif state not in valid_state_set:
                add_error(
                    "state",
                    "invalid_state",
                    f"Invalid grade state '{state_raw}'. Expected one of: {', '.join(valid_states)}.",
                )

            # 5. Validate points_earned
            existing = (
                existing_grades.get((enrollment.pk, assessment.pk))
                if (enrollment is not None and assessment is not None)
                else None
            )
            points_possible = (
                existing.points_possible
                if existing is not None
                else (assessment.points_possible if assessment is not None else None)
            )
            parsed_points: Decimal | None = None
            if state == Grade.State.SCORED:
                if not points_raw:
                    add_error(
                        "points_earned",
                        "required",
                        "Points earned are required when state is 'scored'.",
                    )
                else:
                    try:
                        parsed_points = Decimal(points_raw)
                    except InvalidOperation:
                        add_error(
                            "points_earned",
                            "invalid_number",
                            f"'{points_raw}' is not a valid decimal number.",
                        )
                    else:
                        if not parsed_points.is_finite():
                            add_error(
                                "points_earned",
                                "invalid_number",
                                f"'{points_raw}' is not a finite decimal number.",
                            )
                            parsed_points = None
                        else:
                            exp = parsed_points.as_tuple().exponent
                            if isinstance(exp, int) and exp < -2:
                                add_error(
                                    "points_earned",
                                    "too_many_decimals",
                                    "Points earned may have at most 2 decimal places.",
                                )
                            else:
                                parsed_points = parsed_points.quantize(Decimal("0.01"))
                                if points_possible is not None and (
                                    parsed_points < Decimal(0) or parsed_points > points_possible
                                ):
                                    add_error(
                                        "points_earned",
                                        "out_of_range",
                                        f"Points earned must be between 0 and {points_possible}.",
                                    )
                                elif parsed_points < Decimal(0):
                                    add_error(
                                        "points_earned",
                                        "out_of_range",
                                        "Points earned must be at least 0.",
                                    )
            elif state in valid_state_set and points_raw:
                add_error(
                    "points_earned",
                    "unexpected_points",
                    "Points earned must be empty unless state is 'scored'.",
                )

            # 6. Validate reason length and released-batch reason requirement
            if len(reason) > 255:
                add_error("reason", "too_long", "Reason must be 255 characters or fewer.")

            effective_batch_released = (
                existing.batch.released_at is not None
                if existing is not None
                else target_batch_released
            )

            is_unchanged = (
                existing is not None
                and existing.state == state
                and existing.points_earned == parsed_points
            )
            if effective_batch_released and not is_unchanged and not reason:
                add_error(
                    "reason",
                    "reason_required",
                    "A reason is required when creating or modifying a grade in a released batch.",
                )

            action = "invalid"
            if not row_errors:
                if existing is None:
                    action = "create"
                elif is_unchanged:
                    action = "unchanged"
                else:
                    action = "update"

            if row_errors:
                action = "invalid"
                invalid_rows += 1
                all_errors.extend(row_errors)
            else:
                valid_rows += 1
                if action == "create":
                    create_count += 1
                elif action == "update":
                    update_count += 1
                else:
                    unchanged_count += 1

            preview_rows.append(
                {
                    "row_number": row_number,
                    "student_identifier": student_identifier,
                    "enrollment_id": str(enrollment.pk) if enrollment is not None else None,
                    "assessment_identifier": assessment_identifier,
                    "assessment_id": str(assessment.pk) if assessment is not None else None,
                    "state": state,
                    "points_earned": (
                        f"{parsed_points:.2f}" if parsed_points is not None else None
                    ),
                    "reason": reason,
                    "action": action,
                    "errors": row_errors,
                }
            )

        return {
            "offering": str(offering.pk),
            "sanitized_filename": sanitize_filename(filename),
            "file_checksum": compute_csv_checksum(csv_text),
            "expected_input_revision": offering.input_revision,
            "total_rows": len(preview_rows),
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "create_count": create_count,
            "update_count": update_count,
            "unchanged_count": unchanged_count,
            "can_apply": bool(len(preview_rows) > 0 and invalid_rows == 0),
            "errors": all_errors,
            "rows": preview_rows,
        }

    @transaction.atomic
    def apply(
        self,
        *,
        actor: Any,
        offering: CourseOffering,
        csv_text: str,
        idempotency_key: str,
        file_checksum: str,
        expected_input_revision: int | None = None,
        batch: GradeBatch | None = None,
        batch_name: str = "",
        filename: str = "",
    ) -> tuple[dict[str, Any], bool]:
        """Atomically apply a validated CSV grade import with idempotency and audit logging."""
        effective_actor = actor if actor is not None else self.actor
        cleaned_key = idempotency_key.strip()
        cleaned_checksum = file_checksum.strip().lower()
        computed_checksum = compute_csv_checksum(csv_text)

        locked_offering = (
            CourseOffering.objects.select_for_update().select_related("program").get(pk=offering.pk)
        )

        existing_record = (
            GradeImportRecord.objects.select_for_update()
            .filter(offering=locked_offering, idempotency_key=cleaned_key)
            .first()
        )
        if existing_record is not None:
            if (
                existing_record.file_checksum != computed_checksum
                or existing_record.file_checksum != cleaned_checksum
            ):
                raise GradeImportConflict(
                    code="idempotency_conflict",
                    detail="This idempotency key was already used with a different CSV payload.",
                )
            return existing_record.response_payload, True

        if computed_checksum != cleaned_checksum:
            raise ValidationError(
                {"file_checksum": "CSV content does not match the provided file checksum."}
            )

        if (
            expected_input_revision is not None
            and locked_offering.input_revision != expected_input_revision
        ):
            raise GradeImportConflict(
                code="stale_revision",
                detail="The offering gradebook changed since dry-run preview. Re-run dry-run and retry.",
            )

        sanitized_name = sanitize_filename(filename)
        if batch is not None:
            target_batch = GradeBatch.objects.select_for_update().get(pk=batch.pk)
            if target_batch.offering_id != locked_offering.pk:
                raise ValidationError({"batch": "This batch belongs to a different offering."})
        else:
            resolved_batch_name = (batch_name.strip() or f"CSV Import ({sanitized_name})")[:120]
            target_batch, _ = GradeBatch.objects.get_or_create(
                offering=locked_offering, name=resolved_batch_name
            )
            target_batch = GradeBatch.objects.select_for_update().get(pk=target_batch.pk)

        report = self.dry_run(
            offering=locked_offering,
            csv_text=csv_text,
            batch=target_batch,
            filename=filename,
        )
        if report["invalid_rows"] > 0 or not report["can_apply"]:
            raise ValidationError(
                {
                    "detail": "CSV import failed validation; no grades were written.",
                    "errors": report["errors"],
                }
            )

        enrollment_ids = {row["enrollment_id"] for row in report["rows"] if row["enrollment_id"]}
        assessment_ids = {row["assessment_id"] for row in report["rows"] if row["assessment_id"]}

        existing_grade_rows = list(
            Grade.objects.filter(
                offering=locked_offering,
                enrollment_id__in=enrollment_ids,
                assessment_id__in=assessment_ids,
            ).values("pk", "batch_id")
        )
        batch_ids = {target_batch.pk} | {row["batch_id"] for row in existing_grade_rows}
        locked_batches = {
            b.pk: b
            for b in GradeBatch.objects.select_for_update().filter(pk__in=batch_ids).order_by("pk")
        }
        locked_enrollments = {
            str(e.pk): e
            for e in Enrollment.objects.select_for_update(of=("self",))
            .filter(pk__in=enrollment_ids)
            .order_by("pk")
        }
        assessments_by_id = {str(a.pk): a for a in Assessment.objects.filter(pk__in=assessment_ids)}
        locked_grades = {
            (str(g.enrollment_id), str(g.assessment_id)): g
            for g in Grade.objects.select_for_update(of=("self",))
            .select_related("batch")
            .filter(pk__in=[row["pk"] for row in existing_grade_rows])
            .order_by("pk")
        }

        created_count = 0
        updated_count = 0
        unchanged_count = 0
        any_released_change = False

        for row in report["rows"]:
            enrollment = locked_enrollments[row["enrollment_id"]]
            assessment = assessments_by_id[row["assessment_id"]]
            state = row["state"]
            points_earned = (
                Decimal(row["points_earned"]) if row["points_earned"] is not None else None
            )
            reason = row["reason"]
            existing = locked_grades.get((row["enrollment_id"], row["assessment_id"]))

            if existing is None:
                grade = Grade(
                    offering=locked_offering,
                    enrollment=enrollment,
                    assessment=assessment,
                    batch=target_batch,
                    state=state,
                    points_earned=points_earned,
                    points_possible=assessment.points_possible,
                    version=1,
                )
                try:
                    grade.save()
                except IntegrityError as exc:
                    raise ValidationError(
                        "A grade already exists for this student and assessment."
                    ) from exc
                GradeHistory.objects.create(
                    grade=grade,
                    version=1,
                    old_state="",
                    old_points_earned=None,
                    new_state=state,
                    new_points_earned=points_earned,
                    reason=reason or "csv_import",
                    changed_by=effective_actor,
                )
                created_count += 1
                if target_batch.released_at is not None:
                    any_released_change = True
            else:
                if existing.state == state and existing.points_earned == points_earned:
                    unchanged_count += 1
                    continue

                effective_batch = locked_batches[existing.batch_id]
                old_state, old_points = existing.state, existing.points_earned
                existing.state = state
                existing.points_earned = points_earned
                existing.version += 1
                existing.save()
                GradeHistory.objects.create(
                    grade=existing,
                    version=existing.version,
                    old_state=old_state,
                    old_points_earned=old_points,
                    new_state=state,
                    new_points_earned=points_earned,
                    reason=reason or "csv_import",
                    changed_by=effective_actor,
                )
                updated_count += 1
                if effective_batch.released_at is not None:
                    any_released_change = True

        if any_released_change:
            RevisionTracker.bump(
                program_id=locked_offering.program_id, offering_id=locked_offering.pk
            )
            locked_offering.refresh_from_db(fields=["input_revision"])

        scope = Scope.objects.get(pk=locked_offering.pk)
        AuditEvent.objects.create(
            actor=effective_actor,
            scope=scope,
            action="grades.csv_imported",
            metadata={
                "scope_type": Scope.Kind.OFFERING,
                "offering_id": str(locked_offering.pk),
                "program_id": str(locked_offering.program_id),
                "entity_type": "grade_import",
                "entity_id": cleaned_key,
                "file_checksum": computed_checksum,
                "sanitized_filename": sanitized_name,
                "batch_id": str(target_batch.pk),
                "total_rows": report["total_rows"],
                "created_count": created_count,
                "updated_count": updated_count,
                "unchanged_count": unchanged_count,
                "resulting_input_revision": locked_offering.input_revision,
            },
        )

        response_payload = {
            "offering": str(locked_offering.pk),
            "batch": str(target_batch.pk),
            "batch_name": target_batch.name,
            "batch_released": target_batch.released_at is not None,
            "idempotency_key": cleaned_key,
            "file_checksum": computed_checksum,
            "sanitized_filename": sanitized_name,
            "total_rows": report["total_rows"],
            "created_count": created_count,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "resulting_input_revision": locked_offering.input_revision,
        }

        GradeImportRecord.objects.create(
            offering=locked_offering,
            batch=target_batch,
            actor=effective_actor,
            idempotency_key=cleaned_key,
            file_checksum=computed_checksum,
            sanitized_filename=sanitized_name,
            total_rows=report["total_rows"],
            created_count=created_count,
            updated_count=updated_count,
            unchanged_count=unchanged_count,
            resulting_input_revision=locked_offering.input_revision,
            response_payload=response_payload,
        )

        return response_payload, False
