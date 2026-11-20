"""Tests for the deterministic, idempotent demo seed command (UI-05)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from access.models import AuditEvent, DirectCapabilityGrant, RoleAssignment
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from academic.models import (
    CalculationRun,
    Course,
    CourseOffering,
    Enrollment,
    Grade,
    GradeHistory,
    InstructorAssignment,
    OutcomeScore,
    Program,
    ProgramCourse,
    ProgramMembership,
    ProgramOutcomeSet,
    Publication,
    Syllabus,
)
from academic.services import CalculationService, CohortAnalyticsService

User = get_user_model()


def _snapshot_counts() -> dict[str, int]:
    return {
        "users": User.objects.count(),
        "programs": Program.objects.count(),
        "courses": Course.objects.count(),
        "program_courses": ProgramCourse.objects.count(),
        "offerings": CourseOffering.objects.count(),
        "po_sets": ProgramOutcomeSet.objects.count(),
        "syllabi": Syllabus.objects.count(),
        "enrollments": Enrollment.objects.count(),
        "grades": Grade.objects.count(),
        "grade_history": GradeHistory.objects.count(),
        "calc_runs": CalculationRun.objects.count(),
        "publications": Publication.objects.count(),
        "role_assignments": RoleAssignment.objects.count(),
        "direct_grants": DirectCapabilityGrant.objects.count(),
        "audit_events": AuditEvent.objects.count(),
    }


@pytest.mark.django_db
def test_seed_demo_is_idempotent_and_satisfies_prd_reference_scenario(settings, monkeypatch):
    settings.DEBUG = True
    seed_pass = "test-demo-seed-pass"
    monkeypatch.setenv("DEMO_SEED_PASSWORD", seed_pass)

    call_command("seed_demo")
    first_counts = _snapshot_counts()

    # Second run must be strictly idempotent with zero duplicate records.
    call_command("seed_demo")
    second_counts = _snapshot_counts()
    assert second_counts == first_counts

    # 1. All 4 demo personas can log in.
    for username in (
        "admin@acibadem.edu.tr",
        "emre.karahan@acibadem.edu.tr",
        "selin.kaya@acibadem.edu.tr",
        "deniz.aydin@live.acibadem.edu.tr",
    ):
        client = Client()
        assert client.login(username=username, password=seed_pass), username
        client.logout()

    # 2. Overlapping roles & scoped assignments.
    coord = User.objects.get(username="emre.karahan@acibadem.edu.tr")
    instructor = User.objects.get(username="selin.kaya@acibadem.edu.tr")
    cse_program = Program.objects.get(code="CSE")
    swe_program = Program.objects.get(code="SWE")

    assert RoleAssignment.objects.filter(
        user=coord, scope_id=cse_program.pk, role_id="program-coordinator", revoked_at__isnull=True
    ).exists()
    off_321 = CourseOffering.objects.get(
        program=cse_program,
        course__code="CSE321",
        term__year=2026,
        term__season="fall",
        section="01",
    )
    assert InstructorAssignment.objects.filter(offering=off_321, user=coord).exists()

    off_311_01 = CourseOffering.objects.get(
        program=cse_program,
        course__code="CSE311",
        term__year=2026,
        term__season="fall",
        section="01",
    )
    off_311_02 = CourseOffering.objects.get(
        program=cse_program,
        course__code="CSE311",
        term__year=2026,
        term__season="fall",
        section="02",
    )
    off_214_01 = CourseOffering.objects.get(
        program=cse_program,
        course__code="CSE214",
        term__year=2026,
        term__season="fall",
        section="01",
    )
    for off in (off_311_01, off_311_02, off_214_01):
        assert InstructorAssignment.objects.filter(offering=off, user=instructor).exists()

    # 3. At least 2 active direct capability grants.
    active_grants = DirectCapabilityGrant.objects.filter(user=instructor, revoked_at__isnull=True)
    assert active_grants.count() >= 2
    assert active_grants.filter(scope_id=off_311_01.pk, capability_id="grades.release").exists()
    assert active_grants.filter(scope_id=cse_program.pk, capability_id="outcomes.view").exists()

    # 4. Many-to-many Programs <-> Courses (CSE 214 linked to both CSE and SWE).
    cse214 = Course.objects.get(code="CSE214")
    linked_program_codes = set(
        ProgramCourse.objects.filter(course=cse214).values_list("program__code", flat=True)
    )
    assert {"CSE", "SWE"}.issubset(linked_program_codes)
    assert swe_program.title == "B.Sc. Software Engineering"

    # 5. Versioned PO sets: v1 historical + v2 active with PO1..PO11.
    po_sets = list(ProgramOutcomeSet.objects.filter(program=cse_program).order_by("version"))
    assert [ps.version for ps in po_sets] == [1, 2]
    assert po_sets[1].outcomes.count() == 11
    assert list(po_sets[1].outcomes.order_by("ordering").values_list("code", flat=True)) == [
        f"PO{i}" for i in range(1, 12)
    ]

    # 6. 45 students (5 named + 40 synthetic cohort).
    assert ProgramMembership.objects.filter(program=cse_program).count() == 45
    deniz = User.objects.get(username="deniz.aydin@live.acibadem.edu.tr")
    deniz_membership = ProgramMembership.objects.get(program=cse_program, user=deniz)
    assert deniz_membership.student_number == "2023041018"

    # 7. PRD §5 & §11.4 reference calculation verification (86.0, 82.9, 85.0, 82.9, cumulative 86.9).
    off_pub_student = Publication.objects.get(
        program=cse_program,
        offering=off_311_01,
        audience=Publication.Audience.STUDENT,
        series_version=1,
    )
    off_scores = {
        (row.level, row.outcome_code): row.evidence["display_value"]
        for row in OutcomeScore.objects.filter(run=off_pub_student.run, student=deniz)
    }
    assert off_scores[(OutcomeScore.Level.LO, "LO1")] == "86.0"
    assert off_scores[(OutcomeScore.Level.LO, "LO2")] == "82.9"
    assert off_scores[(OutcomeScore.Level.COURSE_PO, "PO1")] == "85.0"
    assert off_scores[(OutcomeScore.Level.COURSE_PO, "PO2")] == "82.9"

    prog_pub_student = Publication.objects.get(
        program=cse_program,
        offering__isnull=True,
        audience=Publication.Audience.STUDENT,
        series_version=1,
    )
    cum_scores = {
        row.outcome_code: row
        for row in OutcomeScore.objects.filter(
            run=prog_pub_student.run,
            student=deniz,
            level=OutcomeScore.Level.CUMULATIVE_PO,
        )
    }
    assert cum_scores["PO1"].evidence["display_value"] == "86.9"
    assert cum_scores["PO2"].evidence["display_value"] == "82.9"
    assert cum_scores["PO10"].status == OutcomeScore.Status.NOT_ASSESSED
    assert cum_scores["PO11"].status == OutcomeScore.Status.NOT_ASSESSED

    # Verify Deniz can fetch her own published profile over HTTP.
    deniz_client = Client()
    assert deniz_client.login(username="deniz.aydin@live.acibadem.edu.tr", password=seed_pass)
    scores_resp = deniz_client.get(f"/api/v1/publications/{prog_pub_student.pk}/scores/")
    assert scores_resp.status_code == 200
    http_po1 = next(item for item in scores_resp.json() if item["outcome_code"] == "PO1")
    assert http_po1["evidence"]["display_value"] == "86.9"

    # 8. Edge cases in CSE 311-01 + Syllabus v1 approved & v2 draft.
    assert off_311_01.syllabi.filter(version=1, status=Syllabus.Status.APPROVED).exists()
    assert off_311_01.syllabi.filter(version=2, status=Syllabus.Status.DRAFT).exists()

    kerem_mid = Grade.objects.get(
        offering=off_311_01,
        enrollment__student__username="kerem.yilmaz@live.acibadem.edu.tr",
        assessment__title="Midterm",
    )
    assert kerem_mid.state == Grade.State.SCORED
    assert kerem_mid.points_earned == Decimal("0.00")

    ece_mid = Grade.objects.get(
        offering=off_311_01,
        enrollment__student__username="ece.demir@live.acibadem.edu.tr",
        assessment__title="Midterm",
    )
    assert ece_mid.state == Grade.State.EXEMPT

    mert_proj = Grade.objects.get(
        offering=off_311_01,
        enrollment__student__username="mert.celik@live.acibadem.edu.tr",
        assessment__title="Project",
    )
    assert mert_proj.state == Grade.State.MISSING

    zeynep_enr = Enrollment.objects.get(
        offering=off_311_01,
        student__username="zeynep.arslan@live.acibadem.edu.tr",
    )
    assert zeynep_enr.status == Enrollment.Status.WITHDRAWN
    assert zeynep_enr.eligible_for_outcomes is False

    # Fresh offering calculation reflects blocking ABSENT for Mert while preserving Deniz's exact scores.
    live_run, _ = CalculationService().run_offering(offering=off_311_01, actor=coord)
    assert live_run.is_complete_for_publication is False
    mert_lo1 = OutcomeScore.objects.get(
        run=live_run,
        student__username="mert.celik@live.acibadem.edu.tr",
        level=OutcomeScore.Level.LO,
        outcome_code="LO1",
    )
    assert mert_lo1.status == OutcomeScore.Status.INCOMPLETE

    # 9. Historical publications & trend compatibility/incompatibility.
    pub_v1 = Publication.objects.get(idempotency_key="demo-cse-2025-fall-po-v1-faculty")
    pub_spring_v2 = Publication.objects.get(idempotency_key="demo-cse-2026-spring-po-v2-faculty")
    pub_fall_v2 = Publication.objects.get(idempotency_key="demo-cse-2026-fall-po-v2-faculty")

    analytics_svc = CohortAnalyticsService()
    trend = analytics_svc.compare_trends(publications=[pub_spring_v2, pub_fall_v2])
    assert trend["po_set_version"] == 2
    assert len(trend["points"]) == 2

    with pytest.raises(ValidationError) as exc_info:
        analytics_svc.compare_trends(publications=[pub_v1, pub_fall_v2])
    assert exc_info.value.code == "incompatible_po_set_version"

    # Cohort distribution spans all 4 buckets on PO1.
    summary = analytics_svc.cohort_summary(publication=pub_fall_v2)
    po1_summary = next(item for item in summary["outcomes"] if item["code"] == "PO1")
    for bucket in ("<50", "50-69.9", "70-84.9", "85-100"):
        assert po1_summary["distribution"][bucket] > 0

    # 10. Initial Audit Log events (OPS-02).
    audit_actions = set(AuditEvent.objects.values_list("action", flat=True))
    assert {
        "capability.granted",
        "outcomes.published",
        "syllabus.submitted",
        "grade.corrected",
    }.issubset(audit_actions)


@pytest.mark.django_db
def test_seed_demo_refuses_non_debug_environment(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_demo")


@pytest.mark.django_db
def test_seed_demo_requires_password_env_or_flag(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.delenv("DEMO_SEED_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="DEMO_SEED_PASSWORD"):
        call_command("seed_demo")


@pytest.mark.django_db
def test_seed_demo_succeeds_after_seed_acibadem(tmp_path, settings, monkeypatch):
    """seed_demo must coexist cleanly and stay idempotent on a DB already seeded by seed_acibadem."""
    settings.DEBUG = True
    call_command("seed_acibadem", credentials_file=str(tmp_path / "creds.json"))

    monkeypatch.setenv("DEMO_SEED_PASSWORD", "test-demo-seed-pass")
    call_command("seed_demo")
    first_counts = _snapshot_counts()

    call_command("seed_demo")
    assert _snapshot_counts() == first_counts

    deniz = User.objects.get(username="deniz.aydin@live.acibadem.edu.tr")
    prog_pub_student = Publication.objects.get(
        program__code="CSE",
        offering__isnull=True,
        audience=Publication.Audience.STUDENT,
        idempotency_key="demo-cse-2026-fall-po-v2-student",
    )
    po1 = OutcomeScore.objects.get(
        run=prog_pub_student.run,
        student=deniz,
        level=OutcomeScore.Level.CUMULATIVE_PO,
        outcome_code="PO1",
    )
    assert po1.evidence["display_value"] == "86.9"
