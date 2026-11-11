from uuid import uuid4

import pytest
from access.models import AuditEvent, RoleAssignment
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from . import services
from .conftest import NOW, make_report
from .services import (
    ExportNotFound,
    ExportTooLarge,
    ReportExportService,
    ReportGenerationError,
)

pytestmark = pytest.mark.django_db


def service(actor, published, **kwargs):
    return ReportExportService(actor=actor, reader=published["reader"], clock=lambda: NOW, **kwargs)


def export_cohort(world, published, actor, **kwargs):
    return service(actor, published).export(
        publication_id=published["publication_id"],
        format=kwargs.get("format", "csv"),
        scope="cohort",
        program_id=kwargs.get("program_id", world["program_a"].pk),
    )


def export_student(published, actor, **kwargs):
    return service(actor, published).export(
        publication_id=kwargs.get("publication_id", published["publication_id"]),
        format=kwargs.get("format", "csv"),
        scope="student",
    )


def test_student_exports_their_own_published_report_and_it_is_audited(world, published):
    result = export_student(published, world["student"])
    assert result.content_type == "text/csv; charset=utf-8"
    assert result.filename == f"outcome-report-student-{str(published['publication_id'])[:8]}.csv"
    event = AuditEvent.objects.get()
    assert (event.actor, event.scope, event.action) == (
        world["student"],
        world["offering"],
        "reports.exported",
    )
    assert event.metadata["publication_id"] == str(published["publication_id"])
    assert event.metadata["format"] == "csv" and event.metadata["kind"] == "student"
    assert event.metadata["bytes"] == len(result.content)


def test_audit_event_holds_identifiers_and_counts_only(world, published):
    export_student(published, world["student"])
    text = str(AuditEvent.objects.get().metadata)
    for private in ("Computer Engineering", "Engineering knowledge", "84.9", "Student"):
        assert private not in text


def test_a_student_never_receives_another_students_report(world, published):
    # The reader only holds a report for `student`; the requester is always the actor.
    with pytest.raises(ExportNotFound):
        export_student(published, world["other_student"])
    assert not AuditEvent.objects.exists()


def test_unpublished_or_unknown_publication_is_not_found(world, published):
    with pytest.raises(ExportNotFound):
        export_student(published, world["student"], publication_id=uuid4())
    assert not AuditEvent.objects.exists()


def test_user_without_a_student_role_is_denied_a_student_export(world, published):
    for name in ("outsider", "coord_a", "admin"):
        with pytest.raises(PermissionDenied):
            export_student(published, world[name])


def test_student_cannot_export_a_cohort_report(world, published):
    with pytest.raises(PermissionDenied):
        export_cohort(world, published, world["student"])
    with pytest.raises(PermissionDenied):
        export_cohort(world, published, world["outsider"])
    assert not AuditEvent.objects.exists()


def test_coordinator_and_administrator_export_their_program_cohort(world, published):
    for name in ("coord_a", "admin"):
        result = export_cohort(world, published, world[name], format="pdf")
        assert result.content.startswith(b"%PDF-")
    assert AuditEvent.objects.filter(action="reports.exported").count() == 2


def test_coordinator_of_another_program_cannot_tell_the_report_exists(world, published):
    with pytest.raises(ExportNotFound):
        export_cohort(world, published, world["coord_b"])
    assert not AuditEvent.objects.exists()


def test_instructor_is_not_given_program_level_reports(world, published):
    # Offering-level faculty exports need an offering parameter that the contract lacks.
    with pytest.raises(ExportNotFound):
        export_cohort(world, published, world["instructor"])


def test_revoked_access_is_denied_immediately(world, published):
    RoleAssignment.objects.filter(user=world["coord_a"]).update(revoked_at=timezone.now())
    with pytest.raises(PermissionDenied):
        export_cohort(world, published, world["coord_a"])


def test_evidence_is_included_only_where_the_user_may_see_it(world, published):
    with_evidence = export_cohort(world, published, world["coord_a"]).content
    assert b"Formula" in with_evidence
    view_only = export_cohort(world, published, world["viewer"]).content
    assert b"PO1" in view_only and b"Formula" not in view_only
    assert AuditEvent.objects.filter(metadata__evidence=False).count() == 1


def test_reader_data_that_does_not_match_the_request_is_refused(world, published):
    reader, publication_id = published["reader"], published["publication_id"]
    program = world["program_a"].pk
    reader.cohorts[(publication_id, program)] = make_report(
        "cohort", [program], publication_id=uuid4()
    )
    with pytest.raises(ExportNotFound):
        export_cohort(world, published, world["coord_a"])
    reader.cohorts[(publication_id, program)] = make_report(
        "cohort", [world["program_b"].pk], publication_id=publication_id
    )
    with pytest.raises(ExportNotFound):
        export_cohort(world, published, world["coord_a"])
    reader.cohorts[(publication_id, program)] = make_report(
        "student", [program], publication_id=publication_id
    )
    with pytest.raises(ExportNotFound):
        export_cohort(world, published, world["coord_a"])
    assert not AuditEvent.objects.exists()


def test_report_for_scopes_the_student_is_not_in_is_not_served(world, published):
    reader, publication_id = published["reader"], published["publication_id"]
    reader.students[(publication_id, world["student"].pk)] = make_report(
        "student", [world["program_b"].pk], publication_id=publication_id
    )
    with pytest.raises(ExportNotFound):
        export_student(published, world["student"])


def test_oversized_export_is_refused_before_rendering(world, published, settings):
    settings.REPORT_EXPORT_MAX_ROWS = 2
    with pytest.raises(ExportTooLarge):
        export_cohort(world, published, world["coord_a"])
    assert not AuditEvent.objects.exists()


def test_failed_rendering_writes_nothing(world, published, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("renderer exploded")

    monkeypatch.setattr(services, "render_pdf", boom)
    with pytest.raises(ReportGenerationError):
        export_cohort(world, published, world["coord_a"], format="pdf")
    assert not AuditEvent.objects.exists()
    # The same publication can still be exported afterwards.
    assert export_cohort(world, published, world["coord_a"], format="csv").content


def test_rerunning_an_export_gives_equivalent_content(world, published):
    for fmt in ("csv", "pdf"):
        first = export_cohort(world, published, world["coord_a"], format=fmt)
        second = export_cohort(world, published, world["coord_a"], format=fmt)
        assert first.content == second.content
