import datetime as dt
from decimal import Decimal

import pytest
from access.models import RoleAssignment
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.utils import timezone
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
    ProgramOutcome,
    ProgramOutcomeSet,
)
from academic.services import (
    CourseOfferingService,
    EnrollmentService,
    InstructorAssignmentService,
    SyllabusService,
)
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
    ProgramOutcomeSet.objects.get_or_create(
        program=w["program"],
        version=1,
        defaults={
            "status": ProgramOutcomeSet.Status.ACTIVE,
            "effective_date": dt.date(2020, 1, 1),
            "source_reference": "test",
            "activated_at": timezone.now(),
            "activated_by": w["admin"],
        },
    )
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


# ---------------------------------------------------------------------------
# CUR-01: versioned syllabus, learning outcomes, and assessments
# ---------------------------------------------------------------------------


def make_teacher(world, offering):
    teacher = User.objects.create_user("teacher", password="x")
    InstructorAssignmentService(actor=world["admin"]).create(
        offering=offering, user=teacher, assignment_role="instructor"
    )
    return teacher


def make_coordinator(world):
    coordinator = User.objects.create_user("coordinator", password="x")
    grant_role(coordinator, world["program"].pk, "program-coordinator")
    return coordinator


def filled_draft(world, offering, actor):
    syllabus = SyllabusService(actor=actor).create(offering=offering)
    service = SyllabusService(actor=actor)
    service.add_learning_outcome(syllabus=syllabus, code="LO1", description="Design DBs", order=1)
    service.add_assessment(
        syllabus=syllabus, code="MT1", kind="exam", order=1, max_points=Decimal("40.00")
    )
    return syllabus


def test_instructor_can_draft_and_approve_locks(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    syllabus = filled_draft(world, offering, teacher)

    assert syllabus.status == "draft" and syllabus.version == 1
    assert [lo.code for lo in syllabus.learning_outcomes.all()] == ["LO1"]
    assert [a.code for a in syllabus.assessments.all()] == ["MT1"]

    coordinator = make_coordinator(world)
    SyllabusService(actor=coordinator).approve(syllabus=syllabus)
    syllabus.refresh_from_db()
    assert syllabus.status == "approved"
    assert syllabus.approved_by == coordinator
    assert syllabus.approved_at is not None
    offering.refresh_from_db()
    offering.program.refresh_from_db()
    assert offering.input_revision == 1
    assert offering.program.input_revision == 2  # offering creation bumped it once

    # approved configuration is locked
    with pytest.raises(ValidationError):
        SyllabusService(actor=teacher).add_learning_outcome(
            syllabus=syllabus, code="LO2", description="More", order=2
        )
    with pytest.raises(ValidationError):
        SyllabusService(actor=teacher).update_assessment(
            instance=syllabus.assessments.get(), max_points=Decimal("99.00")
        )
    with pytest.raises(ValidationError):
        SyllabusService(actor=coordinator).remove_unused_draft(syllabus=syllabus)


def test_invalid_points_duplicate_codes_and_cross_references_rejected(world):
    offering = make_offering(world)
    other = make_offering(world, section="02")
    teacher = make_teacher(world, offering)
    syllabus = SyllabusService(actor=teacher).create(offering=offering)
    service = SyllabusService(actor=teacher)

    # non-positive max points rejected at both serializer/service level and DB level
    with pytest.raises(ValidationError):
        service.add_assessment(
            syllabus=syllabus, code="HW1", kind="homework", order=1, max_points=Decimal("0.00")
        )
    with pytest.raises(ValidationError):
        service.add_assessment(
            syllabus=syllabus, code="HW1", kind="homework", order=1, max_points=Decimal("-3.00")
        )
    service.add_assessment(
        syllabus=syllabus, code="HW1", kind="homework", order=1, max_points=Decimal("10.00")
    )
    # duplicate code and duplicate order rejected within the same version
    with pytest.raises(ValidationError):
        service.add_assessment(
            syllabus=syllabus, code="HW1", kind="homework", order=2, max_points=Decimal("10.00")
        )
    with pytest.raises(ValidationError):
        service.add_assessment(
            syllabus=syllabus, code="HW2", kind="homework", order=1, max_points=Decimal("10.00")
        )
    service.add_learning_outcome(syllabus=syllabus, code="LO1", description="First", order=1)
    with pytest.raises(ValidationError):
        service.add_learning_outcome(syllabus=syllabus, code="LO1", description="Dup", order=2)
    with pytest.raises(ValidationError):
        service.add_learning_outcome(
            syllabus=syllabus, code="LO2", description="Dup order", order=1
        )

    # cross-syllabus references rejected: the teacher cannot draft for another offering
    # they are not assigned to
    client = APIClient()
    client.force_authenticate(teacher)
    assert (
        client.post(
            "/api/v1/syllabi/",
            {"offering": str(other.pk)},
            format="json",
        ).status_code
        == 403
    )


def test_approval_requires_content_and_authority(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    coordinator = make_coordinator(world)

    # empty draft cannot be approved
    empty = SyllabusService(actor=teacher).create(offering=offering)
    with pytest.raises(ValidationError):
        SyllabusService(actor=coordinator).approve(syllabus=empty)
    service = SyllabusService(actor=teacher)
    service.add_learning_outcome(syllabus=empty, code="LO1", description="D", order=1)
    service.add_assessment(
        syllabus=empty, code="MT1", kind="exam", order=1, max_points=Decimal("40.00")
    )
    syllabus = empty
    # the instructor cannot approve their own syllabus
    client = APIClient()
    client.force_authenticate(teacher)
    assert client.post(f"/api/v1/syllabi/{syllabus.pk}/approve/").status_code == 403
    # an unassigned coordinator cannot approve either
    outsider = User.objects.create_user("outsider-coord", password="x")
    grant_role(outsider, offering.pk, "instructor")
    client.force_authenticate(outsider)
    assert client.post(f"/api/v1/syllabi/{syllabus.pk}/approve/").status_code in (403, 404)
    SyllabusService(actor=coordinator).approve(syllabus=syllabus)
    syllabus.refresh_from_db()
    assert syllabus.approved_by == coordinator


def test_revision_preserves_prior_version(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    coordinator = make_coordinator(world)
    syllabus = filled_draft(world, offering, teacher)
    SyllabusService(actor=coordinator).approve(syllabus=syllabus)

    revision = SyllabusService(actor=teacher).revise(syllabus=syllabus)
    assert revision.status == "draft" and revision.version == 2
    assert revision.offering_id == syllabus.offering_id
    # prior version preserved with its rows
    syllabus.refresh_from_db()
    assert syllabus.status == "approved"
    assert syllabus.learning_outcomes.count() == 1 and syllabus.assessments.count() == 1
    cloned_lo = revision.learning_outcomes.get()
    assert cloned_lo.code == "LO1" and cloned_lo.pk != syllabus.learning_outcomes.get().pk
    cloned_a = revision.assessments.get()
    assert cloned_a.code == "MT1" and cloned_a.pk != syllabus.assessments.get().pk

    # editing the new draft is allowed; editing the locked prior version is not
    service = SyllabusService(actor=teacher)
    service.update_assessment(instance=revision.assessments.get(), max_points=Decimal("60.00"))
    with pytest.raises(ValidationError):
        service.update_assessment(instance=syllabus.assessments.get(), max_points=Decimal("70.00"))
    # second concurrent draft for the same offering is rejected
    with pytest.raises(ValidationError):
        service.revise(syllabus=syllabus)

    # approving the revised version supersedes the prior official one
    SyllabusService(actor=coordinator).approve(syllabus=revision)
    revision.refresh_from_db()
    syllabus.refresh_from_db()
    assert revision.status == "approved"
    assert syllabus.status == "retired"  # superseded, history preserved
    assert set(
        SyllabusService.model.objects.filter(offering=offering, status="approved").values_list(
            "pk", flat=True
        )
    ) == {revision.pk}


def test_unauthorized_scope_cannot_draft_or_read(world):
    offering = make_offering(world)
    stranger = User.objects.create_user("stranger", password="x")

    teacher = make_teacher(world, offering)
    filled_draft(world, offering, teacher)

    client = APIClient()
    client.force_authenticate(stranger)
    assert client.get("/api/v1/syllabi/").data["count"] == 0
    r = client.post("/api/v1/syllabi/", {"offering": str(offering.pk)}, format="json")
    assert r.status_code == 403

    # an instructor assigned to a different offering sees nothing
    other_offering = make_offering(world, section="02")
    other_teacher = User.objects.create_user("other-teacher", password="x")
    InstructorAssignmentService(actor=world["admin"]).create(
        offering=other_offering, user=other_teacher, assignment_role="instructor"
    )
    client.force_authenticate(other_teacher)
    assert client.get("/api/v1/syllabi/").data["count"] == 0


def test_student_sees_only_own_offering_syllabus(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    syllabus = filled_draft(world, offering, teacher)

    client = APIClient()
    client.force_authenticate(world["student"])
    # a draft is invisible: only the coordinator-approved official version is exposed
    assert client.get("/api/v1/syllabi/").data["count"] == 0
    r = client.get(f"/api/v1/syllabi/{syllabus.pk}/")
    assert r.status_code == 404

    coordinator = make_coordinator(world)
    SyllabusService(actor=coordinator).approve(syllabus=syllabus)
    r = client.get("/api/v1/syllabi/")
    assert r.data["count"] == 1
    assert r.data["results"][0]["id"] == str(syllabus.pk)
    r = client.get(f"/api/v1/syllabi/{syllabus.pk}/")
    assert r.status_code == 200 and r.data["status"] == "approved"
    # write attempts still fail: visibility is read-only for students
    assert client.post(f"/api/v1/syllabi/{syllabus.pk}/revise/").status_code == 403

    # a student enrolled in a different offering's world sees nothing here
    stranger = User.objects.create_user("stranger-student", password="x")
    client.force_authenticate(stranger)
    assert client.get("/api/v1/syllabi/").data["count"] == 0


def test_draft_crud_via_http(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    coordinator = make_coordinator(world)
    client = APIClient()
    client.force_authenticate(teacher)

    r = client.post("/api/v1/syllabi/", {"offering": str(offering.pk)}, format="json")
    assert r.status_code == 201, r.data
    sid = r.data["id"]
    assert r.data["version"] == 1 and r.data["status"] == "draft"

    r = client.post(
        f"/api/v1/syllabi/{sid}/learning-outcomes/",
        {"code": "LO1", "description": "Design", "order": 1},
        format="json",
    )
    assert r.status_code == 201, r.data
    lo_id = r.data["id"]
    r = client.post(
        f"/api/v1/syllabi/{sid}/assessments/",
        {"code": "MT1", "kind": "exam", "order": 1, "max_points": "40.00"},
        format="json",
    )
    assert r.status_code == 201, r.data
    a_id = r.data["id"]

    # serializer-level rejection of non-positive points
    r = client.post(
        f"/api/v1/syllabi/{sid}/assessments/",
        {"code": "HW1", "kind": "homework", "order": 2, "max_points": "0.00"},
        format="json",
    )
    assert r.status_code == 400 and "max_points" in r.data

    # duplicate code over HTTP
    r = client.post(
        f"/api/v1/syllabi/{sid}/assessments/",
        {"code": "MT1", "kind": "exam", "order": 3, "max_points": "10.00"},
        format="json",
    )
    assert r.status_code == 400

    # patch a draft child through its owning syllabus
    r = client.patch(
        f"/api/v1/syllabi/{sid}/assessments/{a_id}/",
        {"max_points": "55.00"},
        format="json",
    )
    assert r.status_code == 200 and str(r.data["max_points"]) == "55.00"
    # cross-syllabus child id is not addressable: a LO id is not an assessment id
    r = client.post(
        f"/api/v1/syllabi/{sid}/assessments/{lo_id}/", format="json"
    )  # wrong resource type
    assert r.status_code == 404 or r.status_code == 405

    # detail with children
    r = client.get(f"/api/v1/syllabi/{sid}/")
    assert r.status_code == 200
    assert [lo["code"] for lo in r.data["learning_outcomes"]] == ["LO1"]
    assert [a["code"] for a in r.data["assessments"]] == ["MT1"]

    # list filtered by offering
    r = client.get(f"/api/v1/syllabi/?offering={offering.pk}")
    assert r.data["count"] == 1

    # approve over HTTP as coordinator
    client.force_authenticate(coordinator)
    r = client.post(f"/api/v1/syllabi/{sid}/approve/")
    assert r.status_code == 200, r.data
    assert r.data["status"] == "approved" and r.data["approved_by"] == coordinator.pk

    # after approval the children are locked over HTTP
    client.force_authenticate(teacher)
    r = client.patch(
        f"/api/v1/syllabi/{sid}/assessments/{a_id}/",
        {"max_points": "70.00"},
        format="json",
    )
    assert r.status_code == 400
    r = client.post(
        f"/api/v1/syllabi/{sid}/learning-outcomes/",
        {"code": "LO2", "description": "x", "order": 2},
        format="json",
    )
    assert r.status_code == 400

    # revision over HTTP
    r = client.post(f"/api/v1/syllabi/{sid}/revise/")
    assert r.status_code == 201, r.data
    assert r.data["version"] == 2 and r.data["status"] == "draft"
    assert [a["code"] for a in r.data["assessments"]] == ["MT1"]


def test_only_one_draft_and_one_official_version(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    service = SyllabusService(actor=teacher)
    first = service.create(offering=offering)
    with pytest.raises(ValidationError):
        service.create(offering=offering)

    # retiring an empty draft frees the slot; version numbers never repeat
    service.remove_unused_draft(syllabus=first)
    second = service.create(offering=offering)
    assert second.version == 2

    # an unused draft carrying configuration cannot be retired
    service.add_learning_outcome(syllabus=second, code="LO1", description="d", order=1)
    with pytest.raises(ValidationError):
        service.remove_unused_draft(syllabus=second)


def test_po_sets_authorization_approval_and_official_selection(world):
    from academic.services.syllabi import official_syllabus_for

    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    coordinator = make_coordinator(world)
    syllabus = filled_draft(world, offering, teacher)
    with pytest.raises(ValidationError):
        official_syllabus_for(offering)
    client = APIClient()
    client.force_authenticate(teacher)
    payload = {
        "program": str(world["program"].pk),
        "version": 2,
        "effective_date": "2021-01-01",
        "source_reference": "source",
    }
    assert client.post("/api/v1/po-sets/", payload, format="json").status_code == 403
    client.force_authenticate(coordinator)
    created = client.post("/api/v1/po-sets/", payload, format="json")
    assert created.status_code == 201, created.data
    set_id = created.data["id"]
    assert client.post(f"/api/v1/po-sets/{set_id}/activate/").status_code == 400
    for index in range(1, 12):
        outcome = {
            "code": f"PO{index}",
            "order": index,
            "label": f"Outcome {index}",
            "description": "Definition",
            "source_reference": "source",
        }
        response = client.post(f"/api/v1/po-sets/{set_id}/outcomes/", outcome, format="json")
        assert response.status_code == 201, response.data
    assert (
        client.post(f"/api/v1/po-sets/{set_id}/outcomes/", outcome, format="json").status_code
        == 400
    )
    assert client.post(f"/api/v1/po-sets/{set_id}/activate/").status_code == 200
    assert (
        client.patch(
            f"/api/v1/po-sets/{set_id}/outcomes/{response.data['id']}/",
            {"label": "Changed"},
            format="json",
        ).status_code
        == 400
    )
    with pytest.raises(ValidationError):
        SyllabusService(actor=coordinator).approve(syllabus=syllabus)
    assert syllabus.po_set_version == 1
    client.force_authenticate(teacher)
    bound = client.post(f"/api/v1/syllabi/{syllabus.pk}/bind-active-po-set/")
    assert bound.status_code == 200 and bound.data["po_set_version"] == 2
    SyllabusService(actor=coordinator).approve(syllabus=syllabus)
    assert client.post(f"/api/v1/syllabi/{syllabus.pk}/bind-active-po-set/").status_code == 400
    client.force_authenticate(coordinator)
    assert (
        client.patch(
            f"/api/v1/po-sets/{created.data['id']}/", {"version": 3}, format="json"
        ).status_code
        == 405
    )


def test_official_syllabus_requires_current_active_set(world):
    from academic.services.po_sets import ProgramOutcomeSetService
    from academic.services.syllabi import official_syllabus_for

    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    coordinator = make_coordinator(world)
    draft = filled_draft(world, offering, teacher)
    SyllabusService(actor=coordinator).approve(syllabus=draft)
    assert official_syllabus_for(offering).pk == draft.pk
    new_set = ProgramOutcomeSet.objects.create(
        program=world["program"],
        version=2,
        effective_date=dt.date(2021, 1, 1),
        source_reference="source",
    )
    for index in range(1, 12):
        ProgramOutcome.objects.create(
            po_set=new_set,
            code=f"PO{index}",
            order=index,
            label=f"Outcome {index}",
            description="Definition",
            source_reference="source",
        )
    ProgramOutcomeSetService(actor=coordinator).activate(instance=new_set)
    with pytest.raises(ValidationError):
        official_syllabus_for(offering)
    revision = SyllabusService(actor=teacher).revise(syllabus=draft)
    assert revision.po_set_version == 2
    SyllabusService(actor=coordinator).approve(syllabus=revision)
    assert official_syllabus_for(offering).pk == revision.pk


def test_stale_draft_objects_cannot_mutate_after_approval(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    coordinator = make_coordinator(world)
    draft = filled_draft(world, offering, teacher)
    stale_assessment = draft.assessments.get()
    stale_outcome = draft.learning_outcomes.get()
    SyllabusService(actor=coordinator).approve(syllabus=draft)
    service = SyllabusService(actor=teacher)
    with pytest.raises(ValidationError):
        service.add_learning_outcome(syllabus=draft, code="LO2", description="late", order=2)
    with pytest.raises(ValidationError):
        service.update_assessment(instance=stale_assessment, max_points=Decimal(20))
    with pytest.raises(ValidationError):
        service.update_learning_outcome(instance=stale_outcome, description="late")


def test_draft_children_can_be_removed_but_locked_ones_cannot(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    coordinator = make_coordinator(world)
    syllabus = filled_draft(world, offering, teacher)
    service = SyllabusService(actor=teacher)
    extra = service.add_learning_outcome(syllabus=syllabus, code="LO2", description="x", order=2)
    service.delete_learning_outcome(instance=extra)
    assert syllabus.learning_outcomes.count() == 1
    SyllabusService(actor=coordinator).approve(syllabus=syllabus)
    with pytest.raises(ValidationError):
        service.delete_assessment(instance=syllabus.assessments.get())
    with pytest.raises(ValidationError):
        service.delete_learning_outcome(instance=syllabus.learning_outcomes.get())


def test_locked_rows_reject_direct_model_writes(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    syllabus = filled_draft(world, offering, teacher)
    SyllabusService(actor=make_coordinator(world)).approve(syllabus=syllabus)
    syllabus.refresh_from_db()
    assessment = syllabus.assessments.get()
    assessment.max_points = Decimal("99.00")
    with pytest.raises(ValidationError):
        assessment.save()
    with pytest.raises(ValidationError):
        assessment.delete()
    with pytest.raises(ValidationError):
        syllabus.delete()


def test_db_rejects_approved_syllabus_without_approval_metadata(world):
    from django.db import IntegrityError, transaction

    from academic.models import Syllabus

    offering = make_offering(world)
    draft = SyllabusService(actor=make_teacher(world, offering)).create(offering=offering)
    with pytest.raises(IntegrityError), transaction.atomic():
        Syllabus.objects.filter(pk=draft.pk).update(status="approved")


def test_child_ids_do_not_resolve_across_versions(world):
    offering = make_offering(world)
    teacher = make_teacher(world, offering)
    old = filled_draft(world, offering, teacher)
    SyllabusService(actor=make_coordinator(world)).approve(syllabus=old)
    revision = SyllabusService(actor=teacher).revise(syllabus=old)
    old_assessment = old.assessments.get()
    client = APIClient()
    client.force_authenticate(teacher)
    url = f"/api/v1/syllabi/{revision.pk}/assessments/{old_assessment.pk}/"
    assert client.patch(url, {"max_points": "5.00"}, format="json").status_code == 404
    assert client.delete(url).status_code == 404
    old_assessment.refresh_from_db()
    assert old_assessment.max_points == Decimal("40.00")


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


def test_correction_uses_saved_points_limit_and_leaves_history_unchanged(gb):
    grade = enter(gb)
    gb["assessment"].points_possible = Decimal(20)
    gb["assessment"].save()

    with pytest.raises(ValidationError) as exc:
        GradeService(actor=gb["teacher"]).correct(
            grade=grade, expected_version=1, state="scored", points_earned=Decimal(11)
        )

    assert "points_earned" in exc.value.message_dict
    grade.refresh_from_db()
    assert grade.version == 1 and grade.history.count() == 1


def test_foreign_batch_fails_before_grade_value_validation(gb):
    other = make_offering(gb, section="02")
    batch = GradeBatch.objects.create(offering=other, name="Other")

    with pytest.raises(ValidationError) as exc:
        enter(gb, batch=batch, points=Decimal(11))

    assert "batch" in exc.value.message_dict
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
    payload = {
        "enrollment": str(gb["enrollment"].pk),
        "assessment": str(gb["assessment"].pk),
        "batch": str(gb["batch"].pk),
        "state": "scored",
        "points_earned": "8.00",
    }
    for actor in (stranger, gb["student"]):
        client = APIClient()
        client.force_authenticate(actor)
        response = client.post("/api/v1/grades/", payload, format="json")
        assert response.status_code == 403
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
