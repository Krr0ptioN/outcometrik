from decimal import Decimal

import pytest
from access.models import AuditEvent, RoleAssignment, Scope
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from academic.models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Grade,
    GradeBatch,
    GradeHistory,
    GradeImportRecord,
    Institution,
    Program,
    ProgramCourse,
    ProgramMembership,
)
from academic.services.grade_import import (
    MAX_CSV_BYTES,
    MAX_CSV_ROWS,
    compute_csv_checksum,
    escape_csv_formula,
    sanitize_filename,
)
from academic.services.grades import GradeBatchService


def _grant_role(user, scope_id, role_slug):
    return RoleAssignment.objects.get_or_create(
        user=user, scope_id=scope_id, role_id=role_slug, revoked_at__isnull=True
    )[0]


@pytest.fixture
def import_world(db):
    user_model = get_user_model()
    teacher = user_model.objects.create_user("imp_teacher")
    other_teacher = user_model.objects.create_user("imp_other_teacher")
    student1 = user_model.objects.create_user(
        "imp_student1", first_name="Ada", last_name="Lovelace"
    )
    student2 = user_model.objects.create_user("imp_student2", first_name="Alan", last_name="Turing")
    withdrawn_student = user_model.objects.create_user(
        "imp_withdrawn", first_name="Grace", last_name="Hopper"
    )
    other_student = user_model.objects.create_user(
        "imp_other_student", first_name="Linus", last_name="Torvalds"
    )

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Import University")
    inst = Institution.objects.create(pk=root.pk, code="IMPU", name="Import University")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Engineering")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at="2026-09-01",
        ends_at="2027-01-15",
    )
    course = Course.objects.create(
        home_department=dept, code="CSE310", title="Software Engineering", ects=6, credits=4
    )
    program = Program.objects.create(
        department=dept,
        code="CSE-BS",
        title="B.S. Computer Engineering",
        status=Program.Status.ACTIVE,
    )
    ProgramCourse.objects.create(
        program=program,
        course=course,
        status=ProgramCourse.Status.APPROVED,
        effective_from="2026-01-01",
    )
    offering = CourseOffering.objects.create(
        program=program,
        course=course,
        term=term,
        section="01",
        status=CourseOffering.Status.ACTIVE,
    )
    other_offering = CourseOffering.objects.create(
        program=program,
        course=course,
        term=term,
        section="02",
        status=CourseOffering.Status.ACTIVE,
    )

    _grant_role(teacher, offering.pk, "instructor")
    _grant_role(other_teacher, other_offering.pk, "instructor")

    for stu, num in (
        (student1, "S1001"),
        (student2, "S1002"),
        (withdrawn_student, "S1003"),
        (other_student, "S1004"),
    ):
        ProgramMembership.objects.create(
            program=program,
            user=stu,
            student_number=num,
            status=ProgramMembership.Status.ACTIVE,
        )

    _grant_role(student1, offering.pk, "student")
    _grant_role(student2, offering.pk, "student")
    _grant_role(other_student, other_offering.pk, "student")

    enrollment1 = Enrollment.objects.create(
        offering=offering, student=student1, status=Enrollment.Status.ENROLLED
    )
    enrollment2 = Enrollment.objects.create(
        offering=offering, student=student2, status=Enrollment.Status.ENROLLED
    )
    withdrawn_enrollment = Enrollment.objects.create(
        offering=offering, student=withdrawn_student, status=Enrollment.Status.WITHDRAWN
    )
    other_enrollment = Enrollment.objects.create(
        offering=other_offering, student=other_student, status=Enrollment.Status.ENROLLED
    )

    midterm = Assessment.objects.create(
        offering=offering,
        title="Midterm Exam",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )
    lab = Assessment.objects.create(
        offering=offering,
        title="Lab 1",
        points_possible=Decimal("25.00"),
        status=Assessment.Status.APPROVED,
    )
    draft_assessment = Assessment.objects.create(
        offering=offering,
        title="Draft Quiz",
        points_possible=Decimal("10.00"),
        status=Assessment.Status.DRAFT,
    )
    other_assessment = Assessment.objects.create(
        offering=other_offering,
        title="Other Midterm",
        points_possible=Decimal("100.00"),
        status=Assessment.Status.APPROVED,
    )

    return {
        "teacher": teacher,
        "other_teacher": other_teacher,
        "student1": student1,
        "student2": student2,
        "withdrawn_student": withdrawn_student,
        "other_student": other_student,
        "offering": offering,
        "other_offering": other_offering,
        "enrollment1": enrollment1,
        "enrollment2": enrollment2,
        "withdrawn_enrollment": withdrawn_enrollment,
        "other_enrollment": other_enrollment,
        "midterm": midterm,
        "lab": lab,
        "draft_assessment": draft_assessment,
        "other_assessment": other_assessment,
    }


def _client_for(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def test_dry_run_reports_actionable_errors_and_writes_nothing(import_world):
    offering = import_world["offering"]
    client = _client_for(import_world["teacher"])

    released_batch = GradeBatch.objects.create(offering=offering, name="Released Midterm")
    GradeBatchService().release(batch=released_batch, actor=import_world["teacher"])
    initial_revision = CourseOffering.objects.get(pk=offering.pk).input_revision

    csv_text = "\n".join(
        [
            "student_identifier,assessment,state,points_earned,reason",
            # Row 1: valid scored zero by student_number + assessment title (with reason for released batch)
            "S1001,Midterm Exam,scored,0,Initial released entry",
            # Row 2: duplicate of Row 1 using enrollment UUID + assessment UUID
            f"{import_world['enrollment1'].pk},{import_world['midterm'].pk},scored,50,Dup",
            # Row 3: unknown student
            "NO_SUCH_STUDENT,Midterm Exam,scored,80,Valid reason",
            # Row 4: inactive (withdrawn) enrollment
            "S1003,Midterm Exam,scored,75,Valid reason",
            # Row 5: unapproved assessment
            "S1002,Draft Quiz,scored,5,Valid reason",
            # Row 6: invalid state
            "S1002,Lab 1,unknown_state,,Valid reason",
            # Row 7: out-of-range points
            "S1002,Midterm Exam,scored,120.00,Valid reason",
            # Row 8: non-scored with points
            "imp_student2,Lab 1,missing,10,Valid reason",
            # Row 9: released batch missing reason
            "S1001,Lab 1,exempt,,",
        ]
    )

    resp = client.post(
        "/api/v1/grades/import/dry-run/",
        {
            "offering": str(offering.pk),
            "batch": str(released_batch.pk),
            "csv_text": csv_text,
            "filename": "../evil/grades.csv",
        },
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["can_apply"] is False
    assert data["total_rows"] == 9
    assert data["valid_rows"] == 1
    assert data["invalid_rows"] == 8
    assert data["create_count"] == 1
    assert data["sanitized_filename"] == "grades.csv"
    assert data["file_checksum"] == compute_csv_checksum(csv_text)

    errors_by_row = {row["row_number"]: row["errors"] for row in data["rows"]}
    assert errors_by_row[1] == []
    assert any(
        e["column"] == "assessment" and e["code"] == "duplicate_row" for e in errors_by_row[2]
    )
    assert any(
        e["column"] == "student_identifier" and e["code"] == "not_found" for e in errors_by_row[3]
    )
    assert any(
        e["column"] == "student_identifier" and e["code"] == "inactive_enrollment"
        for e in errors_by_row[4]
    )
    assert any(e["column"] == "assessment" and e["code"] == "unapproved" for e in errors_by_row[5])
    assert any(e["column"] == "state" and e["code"] == "invalid_state" for e in errors_by_row[6])
    assert any(
        e["column"] == "points_earned" and e["code"] == "out_of_range" for e in errors_by_row[7]
    )
    assert any(
        e["column"] == "points_earned" and e["code"] == "unexpected_points"
        for e in errors_by_row[8]
    )
    assert any(e["column"] == "reason" and e["code"] == "reason_required" for e in errors_by_row[9])

    # Zero-write guarantee
    assert Grade.objects.count() == 0
    assert GradeHistory.objects.count() == 0
    assert GradeImportRecord.objects.count() == 0
    assert CourseOffering.objects.get(pk=offering.pk).input_revision == initial_revision


def test_atomic_apply_commits_zero_rows_when_any_row_invalid(import_world):
    offering = import_world["offering"]
    client = _client_for(import_world["teacher"])

    csv_text = "student_identifier,assessment,state,points_earned,reason\nS1001,Midterm Exam,scored,90.50,\nS1002,Midterm Exam,missing,,\nS1001,Lab 1,scored,999.00,"

    resp = client.post(
        "/api/v1/grades/import/apply/",
        {
            "offering": str(offering.pk),
            "csv_text": csv_text,
            "idempotency_key": "imp-atomic-rollback",
            "file_checksum": compute_csv_checksum(csv_text),
            "batch_name": "Should Roll Back",
            "filename": "partial.csv",
        },
        format="json",
    )
    assert resp.status_code == 400
    assert Grade.objects.count() == 0
    assert GradeHistory.objects.count() == 0
    assert GradeBatch.objects.filter(name="Should Roll Back").count() == 0
    assert GradeImportRecord.objects.count() == 0


def test_valid_apply_is_atomic_idempotent_audited_and_unreleased_private(import_world):
    offering = import_world["offering"]
    teacher_client = _client_for(import_world["teacher"])
    student_client = _client_for(import_world["student1"])

    csv_text = "\n".join(
        [
            "student_identifier,assessment,state,points_earned,reason",
            "S1001,Midterm Exam,scored,0,",
            f"{import_world['enrollment2'].pk},{import_world['midterm'].pk},missing,,",
            "imp_student1,Lab 1,scored,22.5,",
        ]
    )
    checksum = compute_csv_checksum(csv_text)

    # 1. Dry-run first
    dry_resp = teacher_client.post(
        "/api/v1/grades/import/dry-run/",
        {"offering": str(offering.pk), "csv_text": csv_text, "filename": "midterm.csv"},
        format="json",
    )
    assert dry_resp.status_code == 200
    dry_data = dry_resp.json()
    assert dry_data["can_apply"] is True
    assert dry_data["create_count"] == 3
    assert dry_data["file_checksum"] == checksum

    # 2. First apply -> 201 Created
    apply_payload = {
        "offering": str(offering.pk),
        "csv_text": csv_text,
        "idempotency_key": "imp-key-001",
        "file_checksum": checksum,
        "expected_input_revision": dry_data["expected_input_revision"],
        "batch_name": "Midterm CSV Batch",
        "filename": "midterm.csv",
    }
    first_resp = teacher_client.post("/api/v1/grades/import/apply/", apply_payload, format="json")
    assert first_resp.status_code == 201
    first_data = first_resp.json()
    assert first_data["created_count"] == 3
    assert first_data["updated_count"] == 0
    assert first_data["unchanged_count"] == 0
    assert first_data["batch_released"] is False
    assert first_data["file_checksum"] == checksum

    assert Grade.objects.count() == 3
    assert GradeHistory.objects.count() == 3
    assert GradeImportRecord.objects.count() == 1
    audit = AuditEvent.objects.filter(action="grades.csv_imported").get()
    assert audit.actor == import_world["teacher"]
    assert audit.scope_id == offering.pk
    assert audit.metadata["file_checksum"] == checksum
    assert audit.metadata["created_count"] == 3
    assert audit.metadata["entity_id"] == "imp-key-001"

    # 3. Unreleased privacy: student cannot see grades before release
    stu_before = student_client.get("/api/v1/grades/")
    assert stu_before.status_code == 200
    assert stu_before.json()["results"] == []

    # 4. Idempotent replay with same key & checksum -> 200 OK, zero duplicate history/audit
    replay_resp = teacher_client.post("/api/v1/grades/import/apply/", apply_payload, format="json")
    assert replay_resp.status_code == 200
    assert replay_resp.json() == first_data
    assert GradeHistory.objects.count() == 3
    assert AuditEvent.objects.filter(action="grades.csv_imported").count() == 1

    # 5. Reusing same idempotency key with modified CSV -> 409 Conflict
    modified_csv = csv_text.replace("22.5", "24.0")
    conflict_resp = teacher_client.post(
        "/api/v1/grades/import/apply/",
        {
            **apply_payload,
            "csv_text": modified_csv,
            "file_checksum": compute_csv_checksum(modified_csv),
        },
        format="json",
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["code"] == "idempotency_conflict"

    # 6. Release batch -> student now sees their grades
    batch = GradeBatch.objects.get(pk=first_data["batch"])
    release_resp = teacher_client.post(f"/api/v1/grade-batches/{batch.pk}/release/")
    assert release_resp.status_code == 200
    stu_after = student_client.get("/api/v1/grades/")
    assert stu_after.status_code == 200
    assert len(stu_after.json()["results"]) == 2


def test_stale_revision_conflict_returns_409(import_world):
    offering = import_world["offering"]
    client = _client_for(import_world["teacher"])

    csv_text = (
        "student_identifier,assessment,state,points_earned,reason\nS1001,Midterm Exam,scored,88.00,"
    )
    checksum = compute_csv_checksum(csv_text)

    # Simulate offering input_revision advancing after dry-run
    CourseOffering.objects.filter(pk=offering.pk).update(input_revision=5)

    resp = client.post(
        "/api/v1/grades/import/apply/",
        {
            "offering": str(offering.pk),
            "csv_text": csv_text,
            "idempotency_key": "imp-stale-001",
            "file_checksum": checksum,
            "expected_input_revision": 4,
            "filename": "stale.csv",
        },
        format="json",
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "stale_revision"
    assert Grade.objects.count() == 0


def test_limits_sanitization_and_formula_escaping(import_world):
    offering = import_world["offering"]
    client = _client_for(import_world["teacher"])

    # Filename sanitization
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("C:\\Users\\test\\grades\x00 final!.csv") == "grades_final_.csv"
    assert sanitize_filename("") == "grades.csv"
    assert len(sanitize_filename("a" * 200 + ".csv")) <= 120

    # Formula escaping
    for prefix in ("=SUM(A1:A2)", "+cmd|' /C calc'!A0", "-1+1", "@SUM(1,2)", "\t=1", "\r=1"):
        assert escape_csv_formula(prefix).startswith("'")
    assert escape_csv_formula("Midterm Exam") == "Midterm Exam"

    # Template endpoint escapes formula-like assessment titles
    import_world["midterm"].title = '=HYPERLINK("http://evil")'
    import_world["midterm"].save()
    tmpl_resp = client.get(f"/api/v1/grades/import/template/?offering={offering.pk}")
    assert tmpl_resp.status_code == 200
    tmpl_data = tmpl_resp.json()
    assert tmpl_data["max_bytes"] == MAX_CSV_BYTES
    assert tmpl_data["max_rows"] == MAX_CSV_ROWS
    assert "'=HYPERLINK" in tmpl_data["sample_csv"]

    # > 5 MB rejected
    oversized_csv = "student_identifier,assessment,state,points_earned\n" + (
        "a" * (MAX_CSV_BYTES + 10)
    )
    resp_bytes = client.post(
        "/api/v1/grades/import/dry-run/",
        {"offering": str(offering.pk), "csv_text": oversized_csv},
        format="json",
    )
    assert resp_bytes.status_code == 400

    # > 10,000 rows rejected
    too_many_rows_csv = "student_identifier,assessment,state,points_earned\n" + "\n".join(
        ["S1001,Lab 1,scored,10"] * (MAX_CSV_ROWS + 1)
    )
    resp_rows = client.post(
        "/api/v1/grades/import/dry-run/",
        {"offering": str(offering.pk), "csv_text": too_many_rows_csv},
        format="json",
    )
    assert resp_rows.status_code == 400


def test_scoped_authorization_denies_unauthorized_actors(import_world):
    offering = import_world["offering"]
    csv_text = "student_identifier,assessment,state,points_earned\nS1001,Midterm Exam,scored,90\n"
    checksum = compute_csv_checksum(csv_text)

    # Unauthenticated -> 401/403
    anon = _client_for(None)
    assert anon.get(f"/api/v1/grades/import/template/?offering={offering.pk}").status_code in (
        401,
        403,
    )
    assert anon.post(
        "/api/v1/grades/import/dry-run/",
        {"offering": str(offering.pk), "csv_text": csv_text},
        format="json",
    ).status_code in (401, 403)
    assert anon.post(
        "/api/v1/grades/import/apply/",
        {
            "offering": str(offering.pk),
            "csv_text": csv_text,
            "idempotency_key": "anon-key",
            "file_checksum": checksum,
        },
        format="json",
    ).status_code in (401, 403)

    # Student and cross-offering instructor -> 403
    for actor in (import_world["student1"], import_world["other_teacher"]):
        client = _client_for(actor)
        assert (
            client.get(f"/api/v1/grades/import/template/?offering={offering.pk}").status_code == 403
        )
        assert (
            client.post(
                "/api/v1/grades/import/dry-run/",
                {"offering": str(offering.pk), "csv_text": csv_text},
                format="json",
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/grades/import/apply/",
                {
                    "offering": str(offering.pk),
                    "csv_text": csv_text,
                    "idempotency_key": f"denied-{actor.username}",
                    "file_checksum": checksum,
                },
                format="json",
            ).status_code
            == 403
        )


def test_apply_updates_skips_unchanged_and_bumps_revision_for_released_batch(import_world):
    offering = import_world["offering"]
    client = _client_for(import_world["teacher"])

    batch = GradeBatch.objects.create(offering=offering, name="Final Batch")
    initial_csv = "student_identifier,assessment,state,points_earned,reason\nS1001,Midterm Exam,scored,70.00,\nS1002,Midterm Exam,missing,,"
    resp1 = client.post(
        "/api/v1/grades/import/apply/",
        {
            "offering": str(offering.pk),
            "batch": str(batch.pk),
            "csv_text": initial_csv,
            "idempotency_key": "imp-upd-1",
            "file_checksum": compute_csv_checksum(initial_csv),
        },
        format="json",
    )
    assert resp1.status_code == 201
    assert resp1.json()["created_count"] == 2

    # Release the batch
    GradeBatchService().release(batch=batch, actor=import_world["teacher"])
    rev_after_release = CourseOffering.objects.get(pk=offering.pk).input_revision

    # Second CSV: S1001 unchanged (no reason needed), S1002 updated with reason
    second_csv = "student_identifier,assessment,state,points_earned,reason\nS1001,Midterm Exam,scored,70.00,\nS1002,Midterm Exam,scored,82.50,Late makeup exam graded"
    dry2 = client.post(
        "/api/v1/grades/import/dry-run/",
        {"offering": str(offering.pk), "batch": str(batch.pk), "csv_text": second_csv},
        format="json",
    )
    assert dry2.status_code == 200
    assert dry2.json()["can_apply"] is True
    assert dry2.json()["unchanged_count"] == 1
    assert dry2.json()["update_count"] == 1

    resp2 = client.post(
        "/api/v1/grades/import/apply/",
        {
            "offering": str(offering.pk),
            "batch": str(batch.pk),
            "csv_text": second_csv,
            "idempotency_key": "imp-upd-2",
            "file_checksum": compute_csv_checksum(second_csv),
            "expected_input_revision": rev_after_release,
        },
        format="json",
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["updated_count"] == 1
    assert data2["unchanged_count"] == 1
    assert data2["resulting_input_revision"] == rev_after_release + 1

    g1 = Grade.objects.get(
        enrollment=import_world["enrollment1"], assessment=import_world["midterm"]
    )
    g2 = Grade.objects.get(
        enrollment=import_world["enrollment2"], assessment=import_world["midterm"]
    )
    assert g1.version == 1
    assert g2.version == 2
    assert g2.points_earned == Decimal("82.50")
    assert GradeHistory.objects.filter(grade=g1).count() == 1
    assert GradeHistory.objects.filter(grade=g2).count() == 2
