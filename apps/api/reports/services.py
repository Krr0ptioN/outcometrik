"""Authorized, audited, read-only report export.

The service never changes publications or results: it reads through a `PublicationReader`,
renders bytes, and writes one append-only audit event.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from access.models import AuditEvent, RoleAssignment, Scope
from access.policy import ResourceContext, authorization
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .csv_export import render_csv
from .domain import Report, count_lines
from .pdf_export import render_pdf
from .readers import PublicationReader, UnavailablePublicationReader

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROWS = 5000
CONTENT_TYPES = {"csv": "text/csv; charset=utf-8", "pdf": "application/pdf"}


class ExportNotFound(Exception):
    """Missing, unpublished or out-of-scope. These are deliberately indistinguishable."""


class ExportTooLarge(Exception):
    """The export exceeds the synchronous size bound."""


class ReportGenerationError(Exception):
    """Rendering failed. Nothing was written; publications are unaffected."""


@dataclass(frozen=True)
class RenderedExport:
    content: bytes
    content_type: str
    filename: str


class ReportExportService:
    def __init__(self, *, actor, reader: PublicationReader | None = None, clock=timezone.now):
        self.actor = actor
        self.reader = reader or UnavailablePublicationReader()
        self.clock = clock

    @property
    def max_rows(self) -> int:
        return getattr(settings, "REPORT_EXPORT_MAX_ROWS", DEFAULT_MAX_ROWS)

    def export(
        self, *, publication_id: UUID, format: str, scope: str, program_id: UUID | None = None
    ) -> RenderedExport:
        if scope == "student":
            report, scopes, include_evidence = self._student_report(publication_id)
        elif scope == "cohort":
            report, scopes, include_evidence = self._cohort_report(publication_id, program_id)
        else:
            raise ExportNotFound
        # Defence in depth: whatever the reader returned must be exactly what was asked for.
        if report.kind != scope or report.header.publication_id != publication_id:
            raise ExportNotFound
        lines = count_lines(report, include_evidence=include_evidence)
        if lines > self.max_rows:
            raise ExportTooLarge
        generated_at = self.clock()
        content = self._render(report, format, include_evidence, generated_at)
        with transaction.atomic():
            AuditEvent.objects.create(
                actor=self.actor,
                scope=scopes[0],
                action="reports.exported",
                # Identifiers and counts only: never names, scores or other report content.
                metadata={
                    "publication_id": str(publication_id),
                    "run_id": str(report.header.run_id),
                    "format": format,
                    "kind": scope,
                    "rows": lines,
                    "evidence": include_evidence,
                    "bytes": len(content),
                },
            )
        return RenderedExport(
            content=content,
            content_type=CONTENT_TYPES[format],
            filename=f"outcome-report-{scope}-{str(publication_id)[:8]}.{format}",
        )

    def _student_report(self, publication_id):
        is_student = RoleAssignment.objects.filter(
            user=self.actor, role_id="student", revoked_at__isnull=True
        ).exists()
        if not is_student:
            raise PermissionDenied("This action is not permitted in this scope.")
        report = self.reader.student_report(publication_id=publication_id, student=self.actor)
        if report is None:
            raise ExportNotFound
        scopes = list(Scope.objects.filter(pk__in=report.scope_ids).order_by("pk"))
        # The reader returns published data only; owner is always the requesting student.
        published = ResourceContext(owner_id=self.actor.pk, published=True)
        released = ResourceContext(owner_id=self.actor.pk, published=True, released=True)
        allowed = [
            s
            for s in scopes
            if authorization.allows(
                principal=self.actor, capability="outcomes.view", scope=s, resource=published
            )
        ]
        if not allowed:
            raise ExportNotFound
        include_evidence = any(
            authorization.allows(
                principal=self.actor, capability="evidence.view", scope=s, resource=released
            )
            for s in allowed
        )
        return report, allowed, include_evidence

    def _cohort_report(self, publication_id, program_id):
        inherited, exact = authorization.scope_ids(self.actor, "outcomes.view")
        if not (inherited or exact):
            # No faculty/coordinator access at all, e.g. a student asking for a cohort report.
            raise PermissionDenied("This action is not permitted in this scope.")
        scope = Scope.objects.filter(pk=program_id).first()
        if scope is None or not authorization.allows(
            principal=self.actor, capability="outcomes.view", scope=scope
        ):
            raise ExportNotFound
        report = self.reader.cohort_report(publication_id=publication_id, program_id=program_id)
        if report is None or program_id not in report.scope_ids:
            raise ExportNotFound
        include_evidence = authorization.allows(
            principal=self.actor, capability="evidence.view", scope=scope
        )
        return report, [scope], include_evidence

    @staticmethod
    def _render(report: Report, format: str, include_evidence: bool, generated_at: datetime):
        render = render_pdf if format == "pdf" else render_csv
        try:
            return render(report, include_evidence=include_evidence, generated_at=generated_at)
        except Exception as exc:
            # Log the failure type only; the report content is private.
            logger.error("Report rendering failed: %s", type(exc).__name__)
            raise ReportGenerationError from exc


class ReportServiceProvider:
    """Composition root: injects the request actor and the publication reader."""

    def __init__(self, reader: PublicationReader | None = None):
        self.reader = reader

    def provide(self, service_class, *, actor):
        return service_class(actor=actor, reader=self.reader)


report_service_provider = ReportServiceProvider()
