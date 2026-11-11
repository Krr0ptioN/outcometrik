import datetime as dt
from decimal import Decimal

import pytest
from access.models import RoleAssignment
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from academic import selectors
from academic.models import (
    AcademicTerm,
    Assessment,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Grade,
    GradeBatch,
    Institution,
    InstructorAssignment,
    Program,
    ProgramCourse,
    ProgramMembership,
)
from academic.services import CourseOfferingService, EnrollmentService
from academic.services.grades import GradeBatchService, GradeService, GradeVersionConflict

pytestmark = pytest.mark.django_db
User = get_user_model()


def grant_role(user, scope_id, role):
    return RoleAssignment.objects.get_or_create(
        user=user, scope_id=scope_id, role_id=role, revoked_at__isnull=True
    )[0]


@pytest.fixture
def admin_client(world):
    client = APIClient()
    client.force_authenticate(world["admin"])
    return client


@pytest.fixture
def world():
    inst = Institution.objects.create(code="ACU", name="Acibadem")
    admin = User.objects.create_user("admin", password="x")
    grant_role(admin, inst.pk, "administrator")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Eng")
    other = Department.objects.create(institution=inst, code="MATH", name="Math")
    program = Program.objects.create(department=dept, code="CENG", title="Computer Eng")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at=dt.date(2026, 9, 1),
        ends_at=dt.date(2027, 1, 15),
    )
    course = Course.objects.create(
        home_department=dept, code="CSE311", title="DB", ects=6, credits=3
    )
    foreign = Course.objects.create(
        home_department=other, code="MATH101", title="Calc", ects=6, credits=4
    )
    link = ProgramCourse.objects.create(
        program=program,
        course=course,
        effective_from=dt.date(2026, 1, 1),
        status="approved",
    )
    student = User.objects.create_user("stu", password="x")
    ProgramMembership.objects.create(program=program, user=student, student_number="S1")
    return {
        "inst": inst,
        "dept": dept,
        "program": program,
        "term": term,
        "course": course,
        "foreign": foreign,
        "link": link,
        "student": student,
        "admin": admin,
    }


def make_offering(w, section="01"):
    offering = CourseOfferingService(actor=w["admin"]).create(
        program=w["program"], course=w["course"], term=w["term"], section=section
    )
    grant_role(w["student"], offering.pk, "student")
    return offering


def test_create_and_browse_structure(admin_client, world):
    from access.models import Scope

    scope = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="X U")
    grant_role(world["admin"], scope.pk, "administrator")
    r = admin_client.post("/api/v1/institutions/", {"code": "X", "name": "X U"}, format="json")
    assert r.status_code == 201
    r = admin_client.post(
        "/api/v1/offerings/",
        {
            "program": str(world["program"].pk),
            "course": str(world["course"].pk),
            "term": str(world["term"].pk),
            "section": "01",
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    url = f"/api/v1/offerings/?program={world['program'].pk}&term={world['term'].pk}"
    r = admin_client.get(url)
    assert r.status_code == 200 and r.data["count"] == 1


def test_duplicates_rejected(admin_client, world):
    term = {
        "institution": str(world["inst"].pk),
        "year": 2026,
        "season": "fall",
        "starts_at": "2026-09-01",
        "ends_at": "2027-01-15",
    }
    assert admin_client.post("/api/v1/terms/", term, format="json").status_code == 400

    link = {
        "program": str(world["program"].pk),
        "course": str(world["course"].pk),
        "effective_from": "2026-01-01",
    }
    assert admin_client.post("/api/v1/program-courses/", link, format="json").status_code == 400

    off = {
        "program": str(world["program"].pk),
        "course": str(world["course"].pk),
        "term": str(world["term"].pk),
        "section": "01",
    }
    assert admin_client.post("/api/v1/offerings/", off, format="json").status_code == 201
    assert admin_client.post("/api/v1/offerings/", off, format="json").status_code == 400

    mem = {
        "program": str(world["program"].pk),
        "user": world["student"].pk,
        "student_number": "S9",
    }
    assert admin_client.post("/api/v1/program-memberships/", mem, format="json").status_code == 400

    offering = CourseOffering.objects.get()
    grant_role(world["student"], offering.pk, "student")
    enr = {"offering": str(offering.pk), "student": world["student"].pk}
    assert admin_client.post("/api/v1/enrollments/", enr, format="json").status_code == 201
    assert admin_client.post("/api/v1/enrollments/", enr, format="json").status_code == 400


def test_offering_requires_approved_active_link(admin_client, world):
    base = {
        "program": str(world["program"].pk),
        "term": str(world["term"].pk),
        "section": "01",
    }
    # unrelated course
    r = admin_client.post(
        "/api/v1/offerings/", {**base, "course": str(world["foreign"].pk)}, format="json"
    )
    assert r.status_code == 400
    # proposed (not yet approved) link
    ProgramCourse.objects.create(
        program=world["program"], course=world["foreign"], effective_from=dt.date(2026, 1, 1)
    )
    r = admin_client.post(
        "/api/v1/offerings/", {**base, "course": str(world["foreign"].pk)}, format="json"
    )
    assert r.status_code == 400
    # inactive link
    world["link"].status = "inactive"
    world["link"].save()
    r = admin_client.post(
        "/api/v1/offerings/", {**base, "course": str(world["course"].pk)}, format="json"
    )
    assert r.status_code == 400
    # the rule also holds for a direct model save, not only the API
    with pytest.raises(ValidationError):
        CourseOffering.objects.create(
            program=world["program"], course=world["course"], term=world["term"], section="99"
        )


def test_enrollment_requires_active_membership(world):
    offering = make_offering(world)
    outsider = User.objects.create_user("out", password="x")
    with pytest.raises(ValidationError):
        EnrollmentService(actor=world["admin"]).create(offering=offering, student=outsider)


def test_input_revision_and_policy(world):
    program = world["program"]
    offering = make_offering(world)
    program.refresh_from_db()
    assert program.input_revision == 1

    enrollment = EnrollmentService(actor=world["admin"]).create(
        offering=offering, student=world["student"]
    )
    program.refresh_from_db()
    offering.refresh_from_db()
    assert (program.input_revision, offering.input_revision) == (2, 1)
    assert enrollment.eligible_for_outcomes
    assert enrollment.eligibility_policy_version == "proposed-v1"

    EnrollmentService(actor=world["admin"]).update_status(
        enrollment=enrollment, status="withdrawn", reason="left"
    )
    program.refresh_from_db()
    offering.refresh_from_db()
    enrollment.refresh_from_db()
    assert (program.input_revision, offering.input_revision) == (3, 2)
    assert not enrollment.eligible_for_outcomes
    assert list(selectors.eligible_roster(offering)) == []
    assert enrollment.status_events.count() == 2

    # a change that does not flip eligibility does not bump the revision
    EnrollmentService(actor=world["admin"]).update_status(
        enrollment=enrollment, status="incomplete"
    )
    program.refresh_from_db()
    assert program.input_revision == 3


def test_withdrawn_enrollment_does_not_bump(world):
    offering = make_offering(world)
    EnrollmentService(actor=world["admin"]).create(
        offering=offering, student=world["student"], status="withdrawn"
    )
    offering.refresh_from_db()
    assert offering.input_revision == 0


def test_patch_enrollment_status_endpoint(admin_client, world):
    offering = make_offering(world)
    enrollment = EnrollmentService(actor=world["admin"]).create(
        offering=offering, student=world["student"]
    )
    r = admin_client.patch(
        f"/api/v1/enrollments/{enrollment.pk}/",
        {"status": "withdrawn", "reason": "x"},
        format="json",
    )
    assert r.status_code == 200 and r.data["eligible_for_outcomes"] is False


def test_nested_roster_route(admin_client, world):
    offering = make_offering(world)
    r = admin_client.post(
        f"/api/v1/offerings/{offering.pk}/enrollments/",
        {"student": world["student"].pk},
        format="json",
    )
    assert r.status_code == 201, r.data
    r = admin_client.get(f"/api/v1/offerings/{offering.pk}/enrollments/")
    assert r.status_code == 200 and r.data["count"] == 1


def test_denied_scope(world):
    offering = make_offering(world)
    EnrollmentService(actor=world["admin"]).create(offering=offering, student=world["student"])

    stranger = User.objects.create_user("s2", password="x", is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(stranger)
    assert client.get("/api/v1/offerings/").data["count"] == 0
    assert client.get(f"/api/v1/offerings/{offering.pk}/").status_code == 404
    r = client.post("/api/v1/institutions/", {"code": "Z", "name": "Z"}, format="json")
    assert r.status_code == 403

    student_client = APIClient()
    student_client.force_authenticate(world["student"])
    assert student_client.get("/api/v1/offerings/").data["count"] == 1
    assert student_client.get("/api/v1/enrollments/").data["count"] == 1

    teacher = User.objects.create_user("t", password="x")
    grant_role(teacher, offering.pk, "instructor")
    InstructorAssignment.objects.create(offering=offering, user=teacher)
    teacher_client = APIClient()
    teacher_client.force_authenticate(teacher)
    assert teacher_client.get("/api/v1/enrollments/").data["count"] == 1

    assert APIClient().get("/api/v1/offerings/").status_code in (401, 403)


def test_history_protected_and_readable(admin_client, world):
    offering = make_offering(world)
    enrollment = EnrollmentService(actor=world["admin"]).create(
        offering=offering, student=world["student"]
    )

    with pytest.raises(ProtectedError):
        offering.delete()
    with pytest.raises(ProtectedError):
        enrollment.delete()
    assert admin_client.delete(f"/api/v1/offerings/{offering.pk}/").status_code == 405

    r = admin_client.patch(
        f"/api/v1/offerings/{offering.pk}/", {"status": "archived"}, format="json"
    )
    assert r.status_code == 200
    r = admin_client.patch(
        f"/api/v1/courses/{world['course'].pk}/",
        {"title": "Renamed", "active": False},
        format="json",
    )
    assert r.status_code == 200

    # archived offering and its roster are still readable after catalog edits
    assert admin_client.get(f"/api/v1/offerings/{offering.pk}/").status_code == 200
    assert Enrollment.objects.filter(offering=offering).count() == 1

    # identity fields cannot be rewritten
    r = admin_client.patch(
        f"/api/v1/offerings/{offering.pk}/",
        {"course": str(world["foreign"].pk)},
        format="json",
    )
    assert r.status_code == 400


def test_coordinator_and_instructor_are_confined_to_assigned_scopes(admin_client, world):

    other_program = Program.objects.create(
        department=world["dept"], code="MATH", title="Mathematics"
    )
    ProgramCourse.objects.create(
        program=other_program,
        course=world["course"],
        effective_from=dt.date(2026, 1, 1),
        status="approved",
    )
    other_offering = CourseOfferingService(actor=world["admin"]).create(
        program=other_program,
        course=world["course"],
        term=world["term"],
        section="02",
    )
    coordinator = User.objects.create_user("coord", password="x")
    grant_role(coordinator, world["program"].pk, "program-coordinator")
    client = APIClient()
    client.force_authenticate(coordinator)
    coordinator_workspace = client.get("/api/v1/workspaces/coordinator/")
    assert coordinator_workspace.status_code == 200
    assert [program["id"] for program in coordinator_workspace.data["programs"]] == [
        str(world["program"].pk)
    ]
    assert client.get(f"/api/v1/programs/{world['program'].pk}/").status_code == 200
    assert client.get(f"/api/v1/programs/{other_program.pk}/").status_code == 404
    assert client.get(f"/api/v1/offerings/{other_offering.pk}/").status_code == 404
    assert (
        client.post(
            f"/api/v1/offerings/{other_offering.pk}/enrollments/",
            {"student": world["student"].pk},
            format="json",
        ).status_code
        == 404
    )

    instructor = User.objects.create_user("teacher", password="x")
    grant_role(instructor, other_offering.pk, "instructor")
    client.force_authenticate(instructor)
    assert client.get(f"/api/v1/offerings/{other_offering.pk}/").status_code == 200
    assert (
        client.patch(
            f"/api/v1/offerings/{make_offering(world).pk}/",
            {"status": "archived"},
            format="json",
        ).status_code
        == 404
    )
    grant_role(coordinator, other_offering.pk, "instructor")
    client.force_authenticate(coordinator)
    coordinator_teaching_view = client.get("/api/v1/workspaces/instructor/")
    assert [item["id"] for item in coordinator_teaching_view.data["offerings"]] == [
        str(other_offering.pk)
    ]


def test_student_sees_only_own_enrollment(admin_client, world):
    offering = make_offering(world)
    other_student = User.objects.create_user("stu2", password="x")
    ProgramMembership.objects.create(
        program=world["program"], user=other_student, student_number="S2"
    )
    grant_role(other_student, offering.pk, "student")
    own = EnrollmentService(actor=world["admin"]).create(
        offering=offering, student=world["student"]
    )
    other = EnrollmentService(actor=world["admin"]).create(offering=offering, student=other_student)
    client = APIClient()
    client.force_authenticate(world["student"])
    assert client.get("/api/v1/enrollments/").data["count"] == 1
    assert client.get(f"/api/v1/enrollments/{own.pk}/").status_code == 200
    assert client.get(f"/api/v1/enrollments/{other.pk}/").status_code == 404


def test_instructor_assignment_creates_audited_access_role(admin_client, world):
    from access.models import AuditEvent, RoleAssignment

    offering = make_offering(world)
    instructor = User.objects.create_user("assigned-teacher", password="x")
    response = admin_client.post(
        "/api/v1/instructor-assignments/",
        {"offering": str(offering.pk), "user": instructor.pk, "assignment_role": "instructor"},
        format="json",
    )
    assert response.status_code == 201, response.data
    assignment = RoleAssignment.objects.get(user=instructor, scope_id=offering.pk)
    assert assignment.role_id == "instructor"
    assert AuditEvent.objects.filter(
        actor=world["admin"], subject=instructor, scope_id=offering.pk, action="role.assigned"
    ).exists()


def test_role_workspaces_limit_instructor_roster_and_student_records(world):
    offering = make_offering(world)
    second_student = User.objects.create_user("second-student", password="x")
    ProgramMembership.objects.create(
        program=world["program"], user=second_student, student_number="S2"
    )
    grant_role(second_student, offering.pk, "student")
    EnrollmentService(actor=world["admin"]).create(offering=offering, student=world["student"])
    EnrollmentService(actor=world["admin"]).create(offering=offering, student=second_student)

    instructor = User.objects.create_user("instructor", password="x")
    grant_role(instructor, offering.pk, "instructor")
    client = APIClient()
    client.force_authenticate(instructor)
    response = client.get("/api/v1/workspaces/instructor/")
    assert response.status_code == 200
    assert [item["id"] for item in response.data["offerings"]] == [str(offering.pk)]
    assert {row["name"] for row in response.data["offerings"][0]["roster"]} == {
        "stu",
        "second-student",
    }

    client.force_authenticate(world["student"])
    response = client.get("/api/v1/workspaces/student/")
    assert response.status_code == 200
    assert [item["enrollment_id"] for item in response.data["courses"]] == [
        str(Enrollment.objects.get(student=world["student"]).pk)
    ]
    assert response.data["outcomes"] == []

    nonstudent = User.objects.create_user("nonstudent", password="x")
    client.force_authenticate(nonstudent)
    assert client.get("/api/v1/workspaces/student/").status_code == 403


@pytest.fixture
def gb(world):
    offering = make_offering(world)
    enrollment = EnrollmentService(actor=world["admin"]).create(
        offering=offering, student=world["student"]
    )
    teacher = User.objects.create_user("grader", password="x")
    grant_role(teacher, offering.pk, "instructor")
    assessment = Assessment.objects.create(
        offering=offering,
        title="Midterm",
        points_possible=Decimal(10),
        status=Assessment.Status.APPROVED,
    )
    batch = GradeBatch.objects.create(offering=offering, name="Midterm")
    return {
        **world,
        "offering": offering,
        "enrollment": enrollment,
        "teacher": teacher,
        "assessment": assessment,
        "batch": batch,
    }


def enter(gb, *, actor=None, state="scored", points=Decimal(8), reason="", **over):
    return GradeService(actor=actor or gb["teacher"]).create(
        **{
            "enrollment": gb["enrollment"],
            "assessment": gb["assessment"],
            "batch": gb["batch"],
            "state": state,
            "points_earned": points,
            "reason": reason,
            **over,
        }
    )


def release(gb):
    GradeBatchService(actor=gb["teacher"]).release(batch=gb["batch"])


def test_zero_is_scored_and_missing_is_not_zero(gb):
    grade = enter(gb, points=Decimal(0))
    assert grade.state == "scored" and grade.points_earned == Decimal(0)
    grade = GradeService(actor=gb["teacher"]).correct(
        grade=grade, expected_version=1, state="missing", points_earned=None
    )
    assert grade.points_earned is None and grade.state == "missing"


@pytest.mark.parametrize(
    ("state", "points"),
    [
        ("scored", Decimal(11)),
        ("scored", Decimal(-1)),
        ("scored", None),
        ("exempt", Decimal(5)),
    ],
)
def test_invalid_values_fail_and_write_nothing(gb, state, points):
    with pytest.raises(ValidationError):
        enter(gb, state=state, points=points)
    assert Grade.objects.count() == 0


def test_inactive_enrollment_fails(gb):
    EnrollmentService(actor=gb["admin"]).update_status(
        enrollment=gb["enrollment"], status="withdrawn", reason="left"
    )
    with pytest.raises(ValidationError):
        enter(gb)
    assert Grade.objects.count() == 0


def test_unapproved_or_foreign_assessment_fails(gb):
    draft = Assessment.objects.create(
        offering=gb["offering"], title="Draft", points_possible=Decimal(10)
    )
    with pytest.raises(ValidationError):
        enter(gb, assessment=draft)

    other = make_offering(gb, section="02")
    foreign = Assessment.objects.create(
        offering=other,
        title="Other",
        points_possible=Decimal(10),
        status=Assessment.Status.APPROVED,
    )
    with pytest.raises(ValidationError):
        enter(gb, assessment=foreign)
    assert Grade.objects.count() == 0


def test_unauthorized_actors_are_denied(gb):
    stranger = User.objects.create_user("stranger", password="x")
    for actor in (stranger, gb["student"]):
        with pytest.raises(PermissionDenied):
            enter(gb, actor=actor)
    assert Grade.objects.count() == 0


def test_stale_version_returns_conflict(gb):
    svc = GradeService(actor=gb["teacher"])
    grade = enter(gb)
    svc.correct(grade=grade, expected_version=1, state="scored", points_earned=Decimal(9))
    with pytest.raises(GradeVersionConflict) as exc:
        svc.correct(grade=grade, expected_version=1, state="scored", points_earned=Decimal(7))
    assert exc.value.current_version == 2
    grade.refresh_from_db()
    assert grade.points_earned == Decimal(9)


def test_post_release_correction_needs_reason_keeps_history_and_bumps_revision(gb):
    svc = GradeService(actor=gb["teacher"])
    grade = enter(gb)
    release(gb)
    gb["offering"].refresh_from_db()
    before = gb["offering"].input_revision

    with pytest.raises(ValidationError):
        svc.correct(grade=grade, expected_version=1, state="scored", points_earned=Decimal(9))
    svc.correct(
        grade=grade,
        expected_version=1,
        state="scored",
        points_earned=Decimal(9),
        reason="Regrade",
    )

    rows = list(grade.history.values_list("version", "old_points_earned", "new_points_earned"))
    assert rows == [(1, None, Decimal(8)), (2, Decimal(8), Decimal(9))]
    gb["offering"].refresh_from_db()
    assert gb["offering"].input_revision > before


def test_unchanged_correction_is_a_noop(gb):
    svc = GradeService(actor=gb["teacher"])
    grade = enter(gb)
    svc.correct(grade=grade, expected_version=1, state="scored", points_earned=Decimal(8))
    grade.refresh_from_db()
    assert grade.version == 1 and grade.history.count() == 1


def test_students_see_only_own_released_grades(gb):
    other = User.objects.create_user("stu2", password="x")
    ProgramMembership.objects.create(program=gb["program"], user=other, student_number="S2")
    grant_role(other, gb["offering"].pk, "student")
    enter(gb)

    as_student = GradeService(actor=gb["student"])
    assert as_student.get_queryset().count() == 0  # unreleased
    release(gb)
    assert as_student.get_queryset().count() == 1
    assert GradeService(actor=other).get_queryset().count() == 0  # cross-student
    assert GradeService(actor=gb["teacher"]).get_queryset().count() == 1


def test_grade_api_conflict_and_visibility(gb):
    grade = enter(gb)
    teacher = APIClient()
    teacher.force_authenticate(gb["teacher"])
    student = APIClient()
    student.force_authenticate(gb["student"])

    # unreleased: hidden from the student, visible to faculty
    assert student.get(f"/api/v1/grades/{grade.pk}/").status_code == 404
    assert teacher.get(f"/api/v1/grades/{grade.pk}/").status_code == 200

    body = {"expected_version": 1, "state": "scored", "points_earned": "9.00"}
    r = teacher.patch(f"/api/v1/grades/{grade.pk}/", body, format="json")
    assert r.status_code == 200 and r.data["version"] == 2
    r = teacher.patch(f"/api/v1/grades/{grade.pk}/", body, format="json")
    assert r.status_code == 409 and r.data["current_version"] == 2

    # released: the student can read it but cannot write it
    release(gb)
    assert student.get(f"/api/v1/grades/{grade.pk}/").status_code == 200
    r = student.patch(
        f"/api/v1/grades/{grade.pk}/",
        {"expected_version": 2, "state": "scored", "points_earned": "10.00", "reason": "x"},
        format="json",
    )
    assert r.status_code == 403
    assert student.get(f"/api/v1/grades/{grade.pk}/history/").status_code == 403
    assert teacher.get(f"/api/v1/grades/{grade.pk}/history/").status_code == 200
