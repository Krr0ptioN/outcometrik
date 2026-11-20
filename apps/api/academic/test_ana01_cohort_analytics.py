import datetime as dt
import json
from decimal import Decimal

import pytest
from access.models import Role, RoleAssignment, Scope
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from academic.controllers.analytics import AnalyticsController
from academic.models import (
    AcademicTerm,
    Assessment,
    CalculationRun,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Grade,
    Institution,
    OutcomeScore,
    Program,
    ProgramCourse,
    ProgramMembership,
    ProgramOutcome,
    ProgramOutcomeSet,
    Publication,
    SyllabusAssessment,
)
from academic.services import (
    CalculationService,
    CohortAnalyticsService,
    EnrollmentService,
    GradeBatchService,
    GradeService,
    PublicationService,
    SyllabusService,
    academic_service_provider,
)


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _enroll(offering, student, actor, *, attempt_number: int = 1) -> Enrollment:
    RoleAssignment.objects.get_or_create(
        user=student,
        role=Role.objects.get(pk="student"),
        scope=Scope.objects.get(pk=offering.pk),
    )
    return EnrollmentService().create(
        offering=offering,
        student=student,
        attempt_number=attempt_number,
        actor=actor,
    )


def _setup_approved_offering(
    *,
    offering,
    po1,
    po2,
    coord,
    student_scores: list[tuple[object, Decimal, Decimal | None]],
    map_po2: bool = True,
):
    """Create approved syllabus, assessments, enrollments, and released grades for an offering."""
    syl_svc = SyllabusService()
    syl = syl_svc.create(offering=offering)
    lo1 = syl_svc.add_learning_outcome(
        syllabus=syl, code="LO-1", description="Fundamentals", order=1
    )
    sa1 = syl_svc.add_assessment(
        syllabus=syl,
        code="EXAM-1",
        kind=SyllabusAssessment.Kind.EXAM,
        order=1,
        max_points=Decimal("100.00"),
        is_required=True,
        is_active=True,
    )
    a_lo_mappings = [
        {
            "assessment": sa1.pk,
            "learning_outcome": lo1.pk,
            "weight": Decimal("100.00"),
            "is_active": True,
        }
    ]
    lo_po_mappings = [
        {
            "learning_outcome": lo1.pk,
            "program_outcome": po1.pk,
            "weight": 4,
            "is_active": True,
        }
    ]

    if map_po2:
        lo2 = syl_svc.add_learning_outcome(syllabus=syl, code="LO-2", description="Design", order=2)
        sa2 = syl_svc.add_assessment(
            syllabus=syl,
            code="PROJ-1",
            kind=SyllabusAssessment.Kind.PROJECT,
            order=2,
            max_points=Decimal("100.00"),
            is_required=True,
            is_active=True,
        )
        a_lo_mappings.append(
            {
                "assessment": sa2.pk,
                "learning_outcome": lo2.pk,
                "weight": Decimal("100.00"),
                "is_active": True,
            }
        )
        lo_po_mappings.append(
            {
                "learning_outcome": lo2.pk,
                "program_outcome": po2.pk,
                "weight": 5,
                "is_active": True,
            }
        )

    syl = syl_svc.replace_assessment_lo_matrix(
        syllabus=syl,
        expected_revision=syl.mapping_revision,
        mappings=a_lo_mappings,
    )
    syl = syl_svc.replace_lo_po_matrix(
        syllabus=syl,
        expected_revision=syl.mapping_revision,
        mappings=lo_po_mappings,
    )
    syl_svc.set_po_contribution(syllabus=syl, program_outcome=po1, weight=4)
    if map_po2:
        syl_svc.set_po_contribution(syllabus=syl, program_outcome=po2, weight=5)

    syl_svc.approve(syllabus=syl, actor=coord)

    a1 = Assessment.objects.create(
        offering=offering,
        title="EXAM-1",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    a2 = (
        Assessment.objects.create(
            offering=offering,
            title="PROJ-1",
            points_possible=Decimal("100.00"),
            status=Assessment.Status.APPROVED,
        )
        if map_po2
        else None
    )

    batch = GradeBatchService().create(offering=offering, name="Final Batch")
    grade_svc = GradeService()
    for student, score1, score2 in student_scores:
        enr = _enroll(offering, student, coord)
        grade_svc.create(
            enrollment=enr,
            assessment=a1,
            batch=batch,
            state=Grade.State.SCORED,
            points_earned=score1,
            actor=coord,
        )
        if a2 is not None and score2 is not None:
            grade_svc.create(
                enrollment=enr,
                assessment=a2,
                batch=batch,
                state=Grade.State.SCORED,
                points_earned=score2,
                actor=coord,
            )
    GradeBatchService().release(batch=batch, actor=coord)
    return batch


@pytest.fixture
def analytics_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user(
        "ana01_admin", email="admin@ana01.edu", first_name="Ada", last_name="Admin"
    )
    coord = user_model.objects.create_user(
        "ana01_coord", email="coord@ana01.edu", first_name="Cora", last_name="Coord"
    )
    other_coord = user_model.objects.create_user(
        "ana01_other_coord", email="other@ana01.edu", first_name="Otto", last_name="Other"
    )
    outsider = user_model.objects.create_user("ana01_outsider", email="outsider@ana01.edu")

    students = [
        user_model.objects.create_user(
            f"ana01_student_{i}",
            email=f"student{i}@ana01.edu",
            first_name=f"StuFirst{i}",
            last_name=f"StuLast{i}",
        )
        for i in range(1, 5)
    ]

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="ANA01 University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="ANAU", name="ANA01 University")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    term_fall = AcademicTerm.objects.create(
        institution=inst,
        year=2025,
        season="fall",
        starts_at="2025-09-01",
        ends_at="2026-01-15",
    )
    term_spring = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="spring",
        starts_at="2026-02-01",
        ends_at="2026-06-15",
    )

    course1 = Course.objects.create(
        home_department=dept, code="CSE301", title="Algorithms", ects=6, credits=4
    )
    course2 = Course.objects.create(
        home_department=dept, code="CSE302", title="Operating Systems", ects=6, credits=4
    )

    program = Program.objects.create(
        department=dept,
        code="CSE-BS",
        title="B.S. in Computer Engineering",
        status=Program.Status.ACTIVE,
    )
    other_program = Program.objects.create(
        department=dept,
        code="EEE-BS",
        title="B.S. in Electrical Engineering",
        status=Program.Status.ACTIVE,
    )

    for c in (course1, course2):
        ProgramCourse.objects.create(
            program=program,
            course=c,
            effective_from="2025-01-01",
            status=ProgramCourse.Status.APPROVED,
        )
    ProgramCourse.objects.create(
        program=other_program,
        course=course1,
        effective_from="2025-01-01",
        status=ProgramCourse.Status.APPROVED,
    )

    RoleAssignment.objects.create(
        user=coord,
        role=Role.objects.get(pk="program-coordinator"),
        scope=Scope.objects.get(pk=program.pk),
    )
    RoleAssignment.objects.create(
        user=other_coord,
        role=Role.objects.get(pk="program-coordinator"),
        scope=Scope.objects.get(pk=other_program.pk),
    )

    for idx, stu in enumerate(students, start=1):
        ProgramMembership.objects.create(
            program=program,
            user=stu,
            student_number=f"2025990{idx}",
            admitted_term=term_fall,
            status=ProgramMembership.Status.ACTIVE,
        )
    ProgramMembership.objects.create(
        program=other_program,
        user=students[0],
        student_number="20258801",
        admitted_term=term_fall,
        status=ProgramMembership.Status.ACTIVE,
    )

    # Program v1 PO-set
    po_set_v1 = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="ANA01 Spec v1",
    )
    po1 = ProgramOutcome.objects.create(
        outcome_set=po_set_v1,
        code="PO-1",
        label="Engineering Fundamentals",
        description="Apply core engineering fundamentals.",
        source_url="https://example.edu/po-1",
        ordering=1,
    )
    po2 = ProgramOutcome.objects.create(
        outcome_set=po_set_v1,
        code="PO-2",
        label="System Design",
        description="Design reliable software systems.",
        source_url="https://example.edu/po-2",
        ordering=2,
    )
    po_set_v1.status = ProgramOutcomeSet.Status.ACTIVE
    po_set_v1.effective_date = dt.date(2025, 1, 1)
    po_set_v1.activated_by = coord
    po_set_v1.activated_at = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    po_set_v1.save()

    # Other program PO-set
    other_po_set = ProgramOutcomeSet.objects.create(
        program=other_program,
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="EEE Spec v1",
    )
    other_po1 = ProgramOutcome.objects.create(
        outcome_set=other_po_set,
        code="PO-1",
        label="Circuits",
        description="Analyze circuits.",
        source_url="https://example.edu/eee-po-1",
        ordering=1,
    )
    other_po_set.status = ProgramOutcomeSet.Status.ACTIVE
    other_po_set.effective_date = dt.date(2025, 1, 1)
    other_po_set.activated_by = other_coord
    other_po_set.activated_at = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    other_po_set.save()

    # Offering 1 (Fall 2025, CSE301): 4 students spanning all 4 buckets for PO-1:
    # 40 (<50), 60 (50-69.9), 80 (70-84.9), 90 (85-100)
    # Mean = 270 / 4 = 67.5, Median = (60 + 80) / 2 = 70.0, Min = 40.0, Max = 90.0
    offering_fall = CourseOffering.objects.create(
        program=program, course=course1, term=term_fall, section="A"
    )
    _setup_approved_offering(
        offering=offering_fall,
        po1=po1,
        po2=po2,
        coord=coord,
        student_scores=[
            (students[0], Decimal("40.00"), Decimal("50.00")),
            (students[1], Decimal("60.00"), Decimal("70.00")),
            (students[2], Decimal("80.00"), Decimal("85.00")),
            (students[3], Decimal("90.00"), Decimal("95.00")),
        ],
    )

    # Offering 2 (Spring 2026, CSE302) under same PO-set v1
    offering_spring = CourseOffering.objects.create(
        program=program, course=course2, term=term_spring, section="A"
    )
    _setup_approved_offering(
        offering=offering_spring,
        po1=po1,
        po2=po2,
        coord=coord,
        student_scores=[
            (students[0], Decimal("55.00"), Decimal("65.00")),
            (students[1], Decimal("75.00"), Decimal("80.00")),
            (students[2], Decimal("85.00"), Decimal("90.00")),
            (students[3], Decimal("95.00"), Decimal("100.00")),
        ],
    )

    calc_svc = CalculationService()
    pub_svc = PublicationService()

    run_fall, _ = calc_svc.run_offering(offering=offering_fall, actor=coord)
    pub_fall, _ = pub_svc.publish(
        actor=coord,
        run=run_fall,
        expected_series_version=0,
        expected_input_hash=run_fall.input_hash,
        audience=Publication.Audience.FACULTY,
        idempotency_key="ana01-fall-v1",
    )

    run_spring, _ = calc_svc.run_offering(offering=offering_spring, actor=coord)
    pub_spring, _ = pub_svc.publish(
        actor=coord,
        run=run_spring,
        expected_series_version=0,
        expected_input_hash=run_spring.input_hash,
        audience=Publication.Audience.FACULTY,
        idempotency_key="ana01-spring-v1",
    )

    # Other program offering & publication
    other_offering = CourseOffering.objects.create(
        program=other_program, course=course1, term=term_fall, section="A"
    )
    _setup_approved_offering(
        offering=other_offering,
        po1=other_po1,
        po2=None,
        coord=other_coord,
        student_scores=[(students[0], Decimal("88.00"), None)],
        map_po2=False,
    )
    other_run, _ = calc_svc.run_offering(offering=other_offering, actor=other_coord)
    other_pub, _ = pub_svc.publish(
        actor=other_coord,
        run=other_run,
        expected_series_version=0,
        expected_input_hash=other_run.input_hash,
        audience=Publication.Audience.FACULTY,
        idempotency_key="ana01-other-v1",
    )

    return {
        "admin": admin,
        "coord": coord,
        "other_coord": other_coord,
        "outsider": outsider,
        "students": students,
        "program": program,
        "other_program": other_program,
        "term_fall": term_fall,
        "term_spring": term_spring,
        "course1": course1,
        "course2": course2,
        "po1": po1,
        "po2": po2,
        "offering_fall": offering_fall,
        "offering_spring": offering_spring,
        "run_fall": run_fall,
        "pub_fall": pub_fall,
        "run_spring": run_spring,
        "pub_spring": pub_spring,
        "other_pub": other_pub,
    }


def test_wireup_resolves_cohort_analytics_service_and_controller(db):
    svc = academic_service_provider.provide(CohortAnalyticsService)
    assert isinstance(svc, CohortAnalyticsService)
    controller = AnalyticsController()
    assert isinstance(controller.service, CohortAnalyticsService)


def test_coordinator_views_po_distributions_with_exact_decimal_stats_and_traceability(
    analytics_world,
):
    w = analytics_world
    resp = _client(w["coord"]).get(
        "/api/v1/analytics/cohort/",
        {"publication_id": str(w["pub_fall"].pk)},
    )
    assert resp.status_code == 200
    assert resp["Cache-Control"] == "no-store"

    data = resp.json()
    # Traceability metadata
    assert data["publication_id"] == str(w["pub_fall"].pk)
    assert data["run_id"] == str(w["run_fall"].pk)
    assert data["series_version"] == 1
    assert data["program_id"] == str(w["program"].pk)
    assert data["term_id"] == str(w["term_fall"].pk)
    assert data["po_set_version"] == 1
    assert data["policy_version"] == w["run_fall"].policy_version
    assert data["publication_status"] == "published"
    assert data["sample_size"] == 4
    assert data["population_size"] == 4
    assert data["coverage"] == "1.0000"
    assert data["exclusions"] == {
        "NOT_ASSESSED": 0,
        "INCOMPLETE": 0,
        "ALL_EXEMPT": 0,
        "UNMAPPED": 0,
    }

    outcomes = {item["code"]: item for item in data["outcomes"]}
    assert list(outcomes.keys()) == ["PO-1", "PO-2"]

    po1 = outcomes["PO-1"]
    assert po1["n"] == 4
    assert po1["population_size"] == 4
    assert po1["coverage"] == "1.0000"
    assert po1["mean"] == "67.5"
    assert po1["median"] == "70.0"
    assert po1["min"] == "40.0"
    assert po1["max"] == "90.0"
    assert po1["distribution"] == {
        "<50": 1,
        "50-69.9": 1,
        "70-84.9": 1,
        "85-100": 1,
    }

    po2 = outcomes["PO-2"]
    # Scores: 50, 70, 85, 95 -> mean 75.0, median 77.5, min 50.0, max 95.0
    assert po2["n"] == 4
    assert po2["mean"] == "75.0"
    assert po2["median"] == "77.5"
    assert po2["min"] == "50.0"
    assert po2["max"] == "95.0"
    assert po2["distribution"] == {
        "<50": 0,
        "50-69.9": 1,
        "70-84.9": 1,
        "85-100": 2,
    }

    # Resolve latest publication by program_id + course_id + term_id
    latest_resp = _client(w["coord"]).get(
        "/api/v1/analytics/cohort/",
        {
            "program_id": str(w["program"].pk),
            "course_id": str(w["course1"].pk),
            "term_id": str(w["term_fall"].pk),
        },
    )
    assert latest_resp.status_code == 200
    assert latest_resp.json()["publication_id"] == str(w["pub_fall"].pk)


def test_incompatible_po_set_version_comparison_returns_400_and_never_blends(analytics_world):
    w = analytics_world

    # Create a v2 PO-set for the same program and a publication under po_set_version=2
    po_set_v2 = ProgramOutcomeSet.objects.create(
        program=w["program"],
        version=2,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="ANA01 Spec v2",
    )
    po1_v2 = ProgramOutcome.objects.create(
        outcome_set=po_set_v2,
        code="PO-1",
        label="Redefined Fundamentals",
        description="Changed PO definition.",
        source_url="https://example.edu/po-1-v2",
        ordering=1,
    )
    po_set_v2.status = ProgramOutcomeSet.Status.ACTIVE
    po_set_v2.effective_date = dt.date(2025, 6, 1)
    po_set_v2.activated_by = w["coord"]
    po_set_v2.activated_at = dt.datetime(2025, 6, 1, tzinfo=dt.UTC)
    po_set_v2.save()

    run_v2 = CalculationRun.objects.create(
        scope_kind=CalculationRun.ScopeKind.PROGRAM,
        program=w["program"],
        po_set_version=2,
        engine_version=w["run_fall"].engine_version,
        policy_version=w["run_fall"].policy_version,
        input_hash="b" * 64,
        manifest={"scope_kind": "program", "offerings": []},
        status=CalculationRun.Status.COMPLETED,
        is_complete_for_publication=True,
        created_by=w["coord"],
    )
    OutcomeScore.objects.create(
        run=run_v2,
        level=OutcomeScore.Level.CUMULATIVE_PO,
        student=w["students"][0],
        program_outcome=po1_v2,
        outcome_code="PO-1",
        value=Decimal("92.000000"),
        coverage=Decimal("1.0000"),
        status=OutcomeScore.Status.OK,
    )
    pub_v2 = Publication.objects.create(
        program=w["program"],
        term=w["term_spring"],
        run=run_v2,
        series_version=1,
        po_set_version=2,
        audience=Publication.Audience.FACULTY,
        input_hash=run_v2.input_hash,
        idempotency_key="ana01-prog-v2",
        published_by=w["coord"],
    )

    # Service-layer check: raises ValidationError with code="incompatible_po_set_version"
    svc = CohortAnalyticsService()
    with pytest.raises(ValidationError) as exc_info:
        svc.compare_trends(publications=[w["pub_fall"], pub_v2])
    assert exc_info.value.code == "incompatible_po_set_version"

    # HTTP trends endpoint: returns 400 Bad Request
    resp = _client(w["coord"]).get(
        "/api/v1/analytics/trends/",
        {"publication_ids": f"{w['pub_fall'].pk},{pub_v2.pk}"},
    )
    assert resp.status_code == 400
    assert resp["Cache-Control"] == "no-store"

    # Admin comparing two different programs also gets 400
    diff_prog_resp = _client(w["admin"]).get(
        "/api/v1/analytics/trends/",
        {"publication_ids": f"{w['pub_fall'].pk},{w['other_pub'].pk}"},
    )
    assert diff_prog_resp.status_code == 400

    # Compatible publications (both po_set_version=1, same program) succeed in chronological order
    ok_resp = _client(w["coord"]).get(
        "/api/v1/analytics/trends/",
        {"publication_ids": f"{w['pub_spring'].pk},{w['pub_fall'].pk}"},
    )
    assert ok_resp.status_code == 200
    body = ok_resp.json()
    assert body["program_id"] == str(w["program"].pk)
    assert body["po_set_version"] == 1
    assert len(body["points"]) == 2
    assert body["points"][0]["publication_id"] == str(w["pub_fall"].pk)
    assert body["points"][0]["run_id"] == str(w["run_fall"].pk)
    assert body["points"][0]["term"]["label"] == "2025-fall"
    assert body["points"][1]["publication_id"] == str(w["pub_spring"].pk)
    assert body["points"][1]["run_id"] == str(w["run_spring"].pk)
    assert body["points"][1]["term"]["label"] == "2026-spring"
    spring_po1 = next(o for o in body["points"][1]["outcomes"] if o["code"] == "PO-1")
    # 55, 75, 85, 95 -> mean = 77.5, median = 80.0
    assert spring_po1["mean"] == "77.5"
    assert spring_po1["median"] == "80.0"
    assert spring_po1["n"] == 4
    assert spring_po1["coverage"] == "1.0000"


def test_excluded_statuses_never_become_zero_and_are_excluded_from_denominators(analytics_world):
    w = analytics_world
    user_model = get_user_model()
    extra_students = [user_model.objects.create_user(f"ana01_excl_stu_{i}") for i in range(1, 3)]
    all_6 = list(w["students"]) + extra_students

    run = CalculationRun.objects.create(
        scope_kind=CalculationRun.ScopeKind.PROGRAM,
        program=w["program"],
        po_set_version=1,
        engine_version=w["run_fall"].engine_version,
        policy_version=w["run_fall"].policy_version,
        input_hash="c" * 64,
        manifest={"scope_kind": "program", "offerings": []},
        status=CalculationRun.Status.COMPLETED,
        is_complete_for_publication=True,
        created_by=w["coord"],
    )

    # PO-1: 2 scored (80, 100 -> mean 90.0, median 90.0), plus 4 excluded:
    # NOT_ASSESSED, INCOMPLETE, ALL_EXEMPT, UNMAPPED.
    # If any excluded row became 0, mean would drop far below 90.0!
    OutcomeScore.objects.bulk_create(
        [
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=all_6[0],
                program_outcome=w["po1"],
                outcome_code="PO-1",
                value=Decimal("80.000000"),
                coverage=Decimal("1.0000"),
                status=OutcomeScore.Status.OK,
            ),
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=all_6[1],
                program_outcome=w["po1"],
                outcome_code="PO-1",
                value=Decimal("100.000000"),
                coverage=Decimal("1.0000"),
                status=OutcomeScore.Status.OK,
            ),
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=all_6[2],
                program_outcome=w["po1"],
                outcome_code="PO-1",
                value=None,
                coverage=Decimal("0.0000"),
                status=OutcomeScore.Status.NOT_ASSESSED,
            ),
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=all_6[3],
                program_outcome=w["po1"],
                outcome_code="PO-1",
                value=None,
                coverage=Decimal("0.5000"),
                status=OutcomeScore.Status.INCOMPLETE,
            ),
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=all_6[4],
                program_outcome=w["po1"],
                outcome_code="PO-1",
                value=None,
                coverage=Decimal("0.0000"),
                status=OutcomeScore.Status.ALL_EXEMPT,
            ),
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=all_6[5],
                program_outcome=w["po1"],
                outcome_code="PO-1",
                value=None,
                coverage=Decimal("0.0000"),
                status=OutcomeScore.Status.UNMAPPED,
            ),
            # PO-2: all excluded -> n=0, mean/median/min/max must all be None (never 0)
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=all_6[0],
                program_outcome=w["po2"],
                outcome_code="PO-2",
                value=None,
                coverage=Decimal("0.0000"),
                status=OutcomeScore.Status.INCOMPLETE,
            ),
        ]
    )

    pub = Publication.objects.create(
        program=w["program"],
        term=w["term_fall"],
        run=run,
        series_version=1,
        po_set_version=1,
        audience=Publication.Audience.FACULTY,
        input_hash=run.input_hash,
        idempotency_key="ana01-excl-test",
        published_by=w["coord"],
    )

    before_count = OutcomeScore.objects.filter(run=run).count()
    resp = _client(w["coord"]).get(
        "/api/v1/analytics/cohort/",
        {"publication_id": str(pub.pk)},
    )
    assert resp.status_code == 200
    assert OutcomeScore.objects.filter(run=run).count() == before_count

    data = resp.json()
    assert data["sample_size"] == 2
    assert data["population_size"] == 6
    assert data["exclusions"] == {
        "NOT_ASSESSED": 1,
        "INCOMPLETE": 2,
        "ALL_EXEMPT": 1,
        "UNMAPPED": 1,
    }

    outcomes = {item["code"]: item for item in data["outcomes"]}
    po1 = outcomes["PO-1"]
    assert po1["n"] == 2
    assert po1["population_size"] == 6
    assert po1["coverage"] == "0.3333"
    assert po1["mean"] == "90.0"
    assert po1["median"] == "90.0"
    assert po1["min"] == "80.0"
    assert po1["max"] == "100.0"
    assert po1["distribution"] == {
        "<50": 0,
        "50-69.9": 0,
        "70-84.9": 1,
        "85-100": 1,
    }
    assert po1["exclusions"] == {
        "NOT_ASSESSED": 1,
        "INCOMPLETE": 1,
        "ALL_EXEMPT": 1,
        "UNMAPPED": 1,
    }

    po2 = outcomes["PO-2"]
    assert po2["n"] == 0
    assert po2["population_size"] == 1
    assert po2["coverage"] == "0.0000"
    assert po2["mean"] is None
    assert po2["median"] is None
    assert po2["min"] is None
    assert po2["max"] is None
    assert po2["distribution"] == {
        "<50": 0,
        "50-69.9": 0,
        "70-84.9": 0,
        "85-100": 0,
    }
    assert po2["exclusions"]["INCOMPLETE"] == 1


def test_unauthorized_programs_and_student_pii_are_excluded(analytics_world):
    w = analytics_world

    # Other coordinator cannot access CSE program by program_id or publication_id
    r1 = _client(w["other_coord"]).get(
        "/api/v1/analytics/cohort/", {"program_id": str(w["program"].pk)}
    )
    assert r1.status_code == 403

    r2 = _client(w["other_coord"]).get(
        "/api/v1/analytics/cohort/", {"publication_id": str(w["pub_fall"].pk)}
    )
    assert r2.status_code == 403

    # Cross-program spoofing: authorized program_id + unauthorized publication_id -> 404
    r3 = _client(w["other_coord"]).get(
        "/api/v1/analytics/cohort/",
        {
            "program_id": str(w["other_program"].pk),
            "publication_id": str(w["pub_fall"].pk),
        },
    )
    assert r3.status_code == 404

    # Trends with one authorized + one unauthorized publication -> 404
    r4 = _client(w["other_coord"]).get(
        "/api/v1/analytics/trends/",
        {"publication_ids": f"{w['other_pub'].pk},{w['pub_fall'].pk}"},
    )
    assert r4.status_code == 404

    # Student and outsider are denied (403)
    for denied_user in (w["students"][0], w["outsider"]):
        resp = _client(denied_user).get(
            "/api/v1/analytics/cohort/", {"publication_id": str(w["pub_fall"].pk)}
        )
        assert resp.status_code == 403
        trends_resp = _client(denied_user).get(
            "/api/v1/analytics/trends/", {"program_id": str(w["program"].pk)}
        )
        assert trends_resp.status_code == 403

    # Authorized response contains zero student-level PII
    ok_resp = _client(w["coord"]).get(
        "/api/v1/analytics/cohort/", {"publication_id": str(w["pub_fall"].pk)}
    )
    assert ok_resp.status_code == 200
    payload = ok_resp.json()

    def _collect_keys(obj) -> set[str]:
        keys: set[str] = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                keys.add(k)
                keys.update(_collect_keys(v))
        elif isinstance(obj, list):
            for item in obj:
                keys.update(_collect_keys(item))
        return keys

    all_keys = _collect_keys(payload)
    for forbidden_key in (
        "student",
        "students",
        "student_id",
        "student_number",
        "username",
        "email",
        "enrollment_id",
    ):
        assert forbidden_key not in all_keys

    serialized = json.dumps(payload)
    for idx, stu in enumerate(w["students"], start=1):
        assert stu.username not in serialized
        assert stu.email not in serialized
        assert stu.first_name not in serialized
        assert stu.last_name not in serialized
        assert f"2025990{idx}" not in serialized


def test_stale_publication_status_is_reported_without_mutating_snapshot(analytics_world):
    w = analytics_world
    # Bump offering input_revision to simulate post-publication change without mutating Publication
    offering = w["offering_fall"]
    offering.input_revision += 1
    offering.save(update_fields=["input_revision", "updated_at"])

    resp = _client(w["coord"]).get(
        "/api/v1/analytics/cohort/", {"publication_id": str(w["pub_fall"].pk)}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["publication_status"] == "stale"
    assert data["publication_id"] == str(w["pub_fall"].pk)
    assert data["run_id"] == str(w["run_fall"].pk)


def test_ui04_measured_zero_and_unassessed_student_stay_distinct(analytics_world):
    """UI-04 acceptance scenario: 1 measured zero (0.0) + 1 unassessed student.

    The PO must report mean="0.0" with n=1, population_size=2, coverage="0.5000",
    and 1 NOT_ASSESSED exclusion separately — never coercing the unassessed student
    into a second zero or inflating n to 2.
    """
    w = analytics_world
    _, current_hash, _ = CalculationService().build_manifest_and_hash(
        scope_kind=CalculationRun.ScopeKind.PROGRAM,
        program=w["program"],
        offering=None,
        lock=False,
    )
    run = CalculationRun.objects.create(
        scope_kind=CalculationRun.ScopeKind.PROGRAM,
        program=w["program"],
        po_set_version=1,
        engine_version=w["run_fall"].engine_version,
        policy_version=w["run_fall"].policy_version,
        input_hash=current_hash,
        manifest={"scope_kind": "program", "offerings": []},
        status=CalculationRun.Status.COMPLETED,
        is_complete_for_publication=True,
        created_by=w["coord"],
    )

    OutcomeScore.objects.bulk_create(
        [
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=w["students"][0],
                program_outcome=w["po1"],
                outcome_code="PO-1",
                value=Decimal("0.000000"),
                coverage=Decimal("1.0000"),
                status=OutcomeScore.Status.OK,
            ),
            OutcomeScore(
                run=run,
                level=OutcomeScore.Level.CUMULATIVE_PO,
                student=w["students"][1],
                program_outcome=w["po1"],
                outcome_code="PO-1",
                value=None,
                coverage=Decimal("0.0000"),
                status=OutcomeScore.Status.NOT_ASSESSED,
            ),
        ]
    )

    pub = Publication.objects.create(
        program=w["program"],
        term=w["term_fall"],
        run=run,
        series_version=2,
        po_set_version=1,
        audience=Publication.Audience.FACULTY,
        input_hash=run.input_hash,
        idempotency_key="ui04-zero-vs-unassessed",
        published_by=w["coord"],
    )

    resp = _client(w["coord"]).get(
        "/api/v1/analytics/cohort/",
        {
            "program_id": str(w["program"].pk),
            "publication_id": str(pub.pk),
        },
    )
    assert resp.status_code == 200
    assert resp["Cache-Control"] == "no-store"

    data = resp.json()
    assert data["publication_id"] == str(pub.pk)
    assert data["run_id"] == str(run.pk)
    assert data["po_set_version"] == 1
    assert data["publication_status"] == "published"
    assert data["sample_size"] == 1
    assert data["population_size"] == 2
    assert data["coverage"] == "0.5000"
    assert data["exclusions"]["NOT_ASSESSED"] == 1

    po1 = next(item for item in data["outcomes"] if item["code"] == "PO-1")
    assert po1["mean"] == "0.0"
    assert po1["median"] == "0.0"
    assert po1["min"] == "0.0"
    assert po1["max"] == "0.0"
    assert po1["n"] == 1
    assert po1["population_size"] == 2
    assert po1["coverage"] == "0.5000"
    assert po1["distribution"] == {
        "<50": 1,
        "50-69.9": 0,
        "70-84.9": 0,
        "85-100": 0,
    }
    assert po1["exclusions"] == {
        "NOT_ASSESSED": 1,
        "INCOMPLETE": 0,
        "ALL_EXEMPT": 0,
        "UNMAPPED": 0,
    }
