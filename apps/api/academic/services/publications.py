"""Immutable outcome publication, stale detection, and version protocol service (CALC-03)."""

from __future__ import annotations

from typing import Any

from access.models import AuditEvent, Scope
from access.policy import AuthorizationService
from django.core.exceptions import ValidationError
from django.db import transaction
from wireup import injectable

from .. import scoping
from ..models import (
    AcademicTerm,
    CalculationRun,
    OutcomeScore,
    Program,
    Publication,
)
from .calculations import CALC_POLICY_VERSION, ENGINE_VERSION, CalculationService


class PublicationConflict(Exception):
    """Raised when a publication attempt violates completeness, hash, version, or idempotency rules."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@injectable
class PublicationService:
    """Publishes validated calculation snapshots with optimistic series locking and idempotency."""

    model = Publication

    def __init__(
        self,
        auth_service: AuthorizationService | None = None,
        calculation_service: CalculationService | None = None,
        *,
        actor: Any = None,
    ):
        self.auth_service = auth_service or AuthorizationService()
        self.calculation_service = calculation_service or CalculationService(
            auth_service=self.auth_service
        )
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Publication.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields and v not in (None, "")}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("-published_at", "-series_version", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Publication.objects.all()
        effective_actor = actor if actor is not None else self.actor
        return (
            scoping.scope_publications(effective_actor, queryset)
            .select_related(
                "program", "offering", "offering__course", "term", "run", "published_by"
            )
            .defer("run__manifest")
        )

    def is_stale(self, *, publication: Publication) -> bool:
        """Dynamically compare publication.input_hash against current manifest hash without mutating."""
        scope_kind = (
            CalculationRun.ScopeKind.OFFERING
            if publication.offering_id is not None
            else CalculationRun.ScopeKind.PROGRAM
        )
        try:
            _, current_hash, current_po_set_version = (
                self.calculation_service.build_manifest_and_hash(
                    scope_kind=scope_kind,
                    program=publication.program,
                    offering=publication.offering,
                    lock=False,
                )
            )
        except ValidationError:
            return True
        return (
            current_hash != publication.input_hash
            or current_po_set_version != publication.po_set_version
        )

    def list_scores(self, *, publication: Publication, actor: Any = None, **filters):
        """Return immutable OutcomeScore rows for a publication, strictly scoped for students."""
        effective_actor = actor if actor is not None else self.actor
        if effective_actor is None or not getattr(effective_actor, "is_authenticated", False):
            return OutcomeScore.objects.none()

        is_staff = scoping.has_staff_publication_access(effective_actor, publication)
        effective_filters = dict(filters)
        if not is_staff:
            if publication.audience != Publication.Audience.STUDENT:
                return OutcomeScore.objects.none()
            effective_filters.pop("student_id", None)
            effective_filters["student"] = effective_actor

        return self.calculation_service.list_scores(run=publication.run, **effective_filters)

    @transaction.atomic
    def publish(
        self,
        *,
        actor: Any,
        run: CalculationRun,
        expected_series_version: int,
        expected_input_hash: str,
        audience: str,
        idempotency_key: str,
        term: AcademicTerm | None = None,
    ) -> tuple[Publication, bool]:
        """Publish a completed CalculationRun. Returns (publication, replayed)."""
        effective_actor = actor if actor is not None else self.actor
        if effective_actor is None or not getattr(effective_actor, "is_authenticated", False):
            raise ValidationError("An authenticated actor is required to publish outcomes.")

        if audience not in (Publication.Audience.FACULTY, Publication.Audience.STUDENT):
            raise ValidationError({"audience": "Audience must be 'faculty' or 'student'."})
        if expected_series_version < 0:
            raise ValidationError(
                {"expected_series_version": "Expected series version must be non-negative."}
            )
        cleaned_key = (idempotency_key or "").strip()
        if not cleaned_key:
            raise ValidationError({"idempotency_key": "Idempotency key may not be blank."})
        cleaned_hash = (expected_input_hash or "").strip().lower()
        if not cleaned_hash:
            raise ValidationError({"expected_input_hash": "Expected input hash may not be blank."})

        run = CalculationRun.objects.select_related("program__department", "offering__term").get(
            pk=run.pk
        )

        if term is not None:
            if run.offering_id is not None and term.pk != run.offering.term_id:
                raise ValidationError({"term": "Term must match the offering's term."})
            if term.institution_id != run.program.department.institution_id:
                raise ValidationError({"term": "Term must belong to the program's institution."})
        effective_term = (
            term
            if term is not None
            else (run.offering.term if run.offering_id is not None else None)
        )

        # Lock Program and CourseOffering(s) in deterministic PK order while rebuilding manifest hash.
        manifest_error: ValidationError | None = None
        current_hash: str | None = None
        current_po_set_version: int | None = None
        try:
            _, current_hash, current_po_set_version = (
                self.calculation_service.build_manifest_and_hash(
                    scope_kind=run.scope_kind,
                    program=run.program,
                    offering=run.offering,
                    lock=True,
                )
            )
        except ValidationError as exc:
            Program.objects.select_for_update().get(pk=run.program_id)
            manifest_error = exc

        # Lock existing publications for this series in deterministic order.
        series_qs = Publication.objects.filter(
            program_id=run.program_id,
            audience=audience,
        )
        if run.offering_id is not None:
            series_qs = series_qs.filter(offering_id=run.offering_id)
        else:
            series_qs = series_qs.filter(offering__isnull=True)
        locked_series = list(series_qs.select_for_update().order_by("series_version", "pk"))

        # Check idempotency key first so safe retries succeed without duplicating series versions.
        existing = next(
            (pub for pub in locked_series if pub.idempotency_key == cleaned_key),
            None,
        )
        if existing is not None:
            if existing.run_id == run.pk and existing.input_hash == cleaned_hash:
                return existing, True
            raise PublicationConflict(
                "idempotency_conflict",
                "Idempotency key was already used with a different publication payload.",
            )

        if manifest_error is not None:
            raise PublicationConflict(
                "stale_input_hash",
                "Current inputs are no longer valid for publication. Recalculate before publishing.",
            )

        if run.status != CalculationRun.Status.COMPLETED or not run.is_complete_for_publication:
            raise PublicationConflict(
                "incomplete_run",
                "Only completed calculation runs that are complete for publication can be published.",
            )

        if run.engine_version != ENGINE_VERSION or run.policy_version != CALC_POLICY_VERSION:
            raise PublicationConflict(
                "version_mismatch",
                "Calculation run engine or policy version does not match the current active versions.",
            )

        if (
            current_hash != run.input_hash
            or current_hash != cleaned_hash
            or current_po_set_version != run.po_set_version
        ):
            raise PublicationConflict(
                "stale_input_hash",
                "Calculation inputs have changed since this run was computed. Recalculate before publishing.",
            )

        current_version = locked_series[-1].series_version if locked_series else 0
        if current_version != expected_series_version:
            raise PublicationConflict(
                "series_version_conflict",
                f"Expected series_version {expected_series_version}, but current version is {current_version}.",
            )

        publication = Publication.objects.create(
            program=run.program,
            offering=run.offering,
            term=effective_term,
            run=run,
            series_version=expected_series_version + 1,
            po_set_version=run.po_set_version,
            audience=audience,
            input_hash=run.input_hash,
            idempotency_key=cleaned_key,
            published_by=effective_actor,
        )

        scope_pk = run.offering_id if run.offering_id is not None else run.program_id
        scope = Scope.objects.get(pk=scope_pk)
        AuditEvent.objects.create(
            actor=effective_actor,
            scope=scope,
            action="outcomes.published",
            metadata={
                "publication_id": str(publication.pk),
                "run_id": str(run.pk),
                "program_id": str(run.program_id),
                "offering_id": str(run.offering_id) if run.offering_id is not None else None,
                "term_id": str(effective_term.pk) if effective_term is not None else None,
                "audience": audience,
                "series_version": publication.series_version,
                "po_set_version": publication.po_set_version,
                "input_hash": publication.input_hash,
                "idempotency_key": publication.idempotency_key,
            },
        )
        return publication, False
