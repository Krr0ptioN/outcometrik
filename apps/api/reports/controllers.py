from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .serializers import ExportQuerySerializer
from .services import (
    ExportNotFound,
    ExportTooLarge,
    ReportExportService,
    ReportGenerationError,
    report_service_provider,
)


class ExportTooLargeError(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "This export is too large to download directly."
    default_code = "export_too_large"


class ExportFailedError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The report could not be generated. Published results are not affected."
    default_code = "export_failed"


class JSONErrorNegotiation(BaseContentNegotiation):
    """Always negotiate JSON for errors.

    The contract's `format=csv|pdf` query parameter would otherwise be read by DRF as its
    own response-format override and fail with 404 before the view runs. Successful
    responses are plain file responses, so only error bodies are negotiated.
    """

    def select_parser(self, request, parsers):
        return parsers[0] if parsers else None

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class ReportExportController(APIView):
    """GET /api/v1/reports/exports/ — thin HTTP adapter; the service owns every decision."""

    permission_classes = [IsAuthenticated]
    service_provider = report_service_provider
    content_negotiation_class = JSONErrorNegotiation

    def get(self, request):
        query = ExportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        service = self.service_provider.provide(ReportExportService, actor=request.user)
        try:
            export = service.export(**query.validated_data)
        except ExportNotFound as exc:
            raise NotFound from exc
        except ExportTooLarge as exc:
            raise ExportTooLargeError from exc
        except ReportGenerationError as exc:
            raise ExportFailedError from exc
        response = HttpResponse(export.content, content_type=export.content_type)
        response["Content-Disposition"] = f'attachment; filename="{export.filename}"'
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
