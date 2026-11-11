from uuid import uuid4

import pytest
from access.models import AuditEvent
from rest_framework.test import APIClient

from . import services
from .controllers import ReportExportController
from .services import ReportServiceProvider

pytestmark = pytest.mark.django_db
URL = "/api/v1/reports/exports/"


@pytest.fixture(autouse=True)
def wired(published, monkeypatch):
    monkeypatch.setattr(
        ReportExportController, "service_provider", ReportServiceProvider(published["reader"])
    )


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client


def get(client, **query):
    return client.get(URL, query)


def student_query(published, **extra):
    return {
        "publication_id": str(published["publication_id"]),
        "format": "csv",
        "scope": "student",
        **extra,
    }


def cohort_query(world, published, **extra):
    return {
        "publication_id": str(published["publication_id"]),
        "format": "pdf",
        "scope": "cohort",
        "program_id": str(world["program_a"].pk),
        **extra,
    }


def test_requires_sign_in(published):
    response = get(client_for(), **student_query(published))
    assert response.status_code in (401, 403)


def test_student_downloads_a_csv_with_safe_headers(world, published):
    response = get(client_for(world["student"]), **student_query(published))
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"].startswith(
        'attachment; filename="outcome-report-student-'
    )
    assert response["Cache-Control"] == "no-store"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert AuditEvent.objects.filter(actor=world["student"], action="reports.exported").count() == 1


def test_coordinator_downloads_a_pdf(world, published):
    response = get(client_for(world["coord_a"]), **cohort_query(world, published))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


@pytest.mark.parametrize(
    "change, field",
    [
        ({"publication_id": "nope"}, "publication_id"),
        ({"format": "xlsx"}, "format"),
        ({"scope": "everyone"}, "scope"),
        ({"program_id": None}, "program_id"),  # cohort without a program
    ],
)
def test_invalid_query_is_a_400_naming_the_field(world, published, change, field):
    query = {**cohort_query(world, published), **change}
    query = {k: v for k, v in query.items() if v is not None}
    response = get(client_for(world["coord_a"]), **query)
    assert response.status_code == 400 and field in response.json()


def test_student_export_rejects_a_program(world, published):
    query = student_query(published, program_id=str(world["program_a"].pk))
    response = get(client_for(world["student"]), **query)
    assert response.status_code == 400 and "program_id" in response.json()


def test_student_cannot_request_a_cohort_report_403(world, published):
    response = get(client_for(world["student"]), **cohort_query(world, published))
    assert response.status_code == 403


def test_other_programs_and_unknown_publications_are_404(world, published):
    other = get(client_for(world["coord_b"]), **cohort_query(world, published))
    unknown = get(
        client_for(world["coord_a"]), **cohort_query(world, published, publication_id=str(uuid4()))
    )
    assert other.status_code == unknown.status_code == 404
    assert other.json() == unknown.json()  # no hint that the report exists
    assert not AuditEvent.objects.exists()


def test_default_wiring_reports_everything_as_not_found(world, published, monkeypatch):
    monkeypatch.setattr(
        ReportExportController, "service_provider", services.report_service_provider
    )
    response = get(client_for(world["coord_a"]), **cohort_query(world, published))
    assert response.status_code == 404


def test_too_large_is_413(world, published, settings):
    settings.REPORT_EXPORT_MAX_ROWS = 1
    response = get(client_for(world["coord_a"]), **cohort_query(world, published))
    assert response.status_code == 413


def test_render_failure_is_503_without_leaking_details(world, published, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail for student")

    monkeypatch.setattr(services, "render_pdf", boom)
    response = get(client_for(world["coord_a"]), **cohort_query(world, published))
    assert response.status_code == 503
    assert "secret" not in response.content.decode()
    assert not AuditEvent.objects.exists()
