"""HTTP controller for read-only cohort analytics and trend comparisons (ANA-01)."""

from __future__ import annotations

import uuid

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..decorators import controller, get, require_permission
from ..models import Publication
from ..services import CohortAnalyticsService, academic_service_provider


def _extract_publication_ids(query_params) -> list[str]:
    raw_values = query_params.getlist("publication_ids") if hasattr(query_params, "getlist") else []
    if not raw_values and query_params.get("publication_ids"):
        raw_values = [query_params.get("publication_ids")]
    ids: list[str] = []
    for raw in raw_values:
        for part in str(raw).split(","):
            cleaned = part.strip()
            if cleaned:
                ids.append(cleaned)
    return ids


def _resolve_analytics_program_scope(self, request, *args, **kwargs):
    """Resolve the target program scope from query parameters for guard enforcement."""
    params = getattr(request, "query_params", getattr(request, "GET", {}))
    program_id = params.get("program") or params.get("program_id")
    if program_id:
        try:
            return uuid.UUID(str(program_id).strip())
        except (ValueError, TypeError, AttributeError):
            return None

    pub_id = params.get("publication_id")
    if pub_id:
        try:
            uid = uuid.UUID(str(pub_id).strip())
        except (ValueError, TypeError, AttributeError):
            return None
        return Publication.objects.filter(pk=uid).values_list("program_id", flat=True).first()

    pub_ids = _extract_publication_ids(params)
    if pub_ids:
        try:
            uid = uuid.UUID(pub_ids[0])
        except (ValueError, TypeError, AttributeError):
            return None
        return Publication.objects.filter(pk=uid).values_list("program_id", flat=True).first()

    return None


@controller("analytics", basename="analytics")
class AnalyticsController(viewsets.GenericViewSet):
    """Read-only HTTP surface for published cohort analytics and PO-set-safe trends."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def __init__(self, service: CohortAnalyticsService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(CohortAnalyticsService)

    @get("cohort", url_name="cohort")
    @require_permission(
        "outcomes.view",
        scope_field="program",
        scope_getter=_resolve_analytics_program_scope,
    )
    def cohort(self, request, *args, **kwargs):
        params = request.query_params
        program_id = params.get("program") or params.get("program_id")
        publication_id = params.get("publication_id")
        course_id = params.get("course_id")
        term_id = params.get("term_id")
        audience = params.get("audience")

        publication = self.service.resolve_publication(
            actor=request.user,
            publication_id=publication_id,
            program_id=program_id,
            course_id=course_id,
            term_id=term_id,
            audience=audience,
        )
        summary = self.service.cohort_summary(
            publication=publication,
            course_id=course_id,
            term_id=term_id,
        )
        return Response(summary)

    @get("trends", url_name="trends")
    @require_permission(
        "outcomes.view",
        scope_field="program",
        scope_getter=_resolve_analytics_program_scope,
    )
    def trends(self, request, *args, **kwargs):
        params = request.query_params
        program_id = params.get("program") or params.get("program_id")
        publication_ids = _extract_publication_ids(params) or None
        po_set_version = params.get("po_set_version")
        audience = params.get("audience")
        course_id = params.get("course_id")

        publications = self.service.resolve_publications_for_trends(
            actor=request.user,
            publication_ids=publication_ids,
            program_id=program_id,
            po_set_version=po_set_version,
            audience=audience,
            course_id=course_id,
        )
        result = self.service.compare_trends(publications=publications)
        return Response(result)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
