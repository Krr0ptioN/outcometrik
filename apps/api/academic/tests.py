import datetime as dt

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from academic import selectors, services
from academic.models import (
    AcademicTerm,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Institution,
    InstructorAssignment,
    Program,
    ProgramCourse,
    ProgramMembership,
)

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def staff():
    return User.objects.create_user("staff", password="x", is_staff=True)


@pytest.fixture
def admin_client(staff):
    client = APIClient()
    client.force_authenticate(staff)
    return client


@pytest.fixture
def world():
    inst = Institution.objects.create(code="ACU", name="Acibadem")
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
    }


def make_offering(w, section="01"):
    return services.create_offering(
        program=w["program"], course=w["course"], term=w["term"], section=section
    )


def test_create_and_browse_structure(admin_client, world):
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
        services.create_enrollment(offering=offering, student=outsider)


def test_input_revision_and_policy(world):
    program = world["program"]
    offering = make_offering(world)
    program.refresh_from_db()
    assert program.input_revision == 1

    enrollment = services.create_enrollment(offering=offering, student=world["student"])
    program.refresh_from_db()
    offering.refresh_from_db()
    assert (program.input_revision, offering.input_revision) == (2, 1)
    assert enrollment.eligible_for_outcomes
    assert enrollment.eligibility_policy_version == "proposed-v1"

    services.update_enrollment_status(enrollment=enrollment, status="withdrawn", reason="left")
    program.refresh_from_db()
    offering.refresh_from_db()
    enrollment.refresh_from_db()
    assert (program.input_revision, offering.input_revision) == (3, 2)
    assert not enrollment.eligible_for_outcomes
    assert list(selectors.eligible_roster(offering)) == []
    assert enrollment.status_events.count() == 2

    # a change that does not flip eligibility does not bump the revision
    services.update_enrollment_status(enrollment=enrollment, status="incomplete")
    program.refresh_from_db()
    assert program.input_revision == 3


def test_withdrawn_enrollment_does_not_bump(world):
    offering = make_offering(world)
    services.create_enrollment(offering=offering, student=world["student"], status="withdrawn")
    offering.refresh_from_db()
    assert offering.input_revision == 0


def test_patch_enrollment_status_endpoint(admin_client, world):
    offering = make_offering(world)
    enrollment = services.create_enrollment(offering=offering, student=world["student"])
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
    services.create_enrollment(offering=offering, student=world["student"])

    stranger = User.objects.create_user("s2", password="x")
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
    InstructorAssignment.objects.create(offering=offering, user=teacher)
    teacher_client = APIClient()
    teacher_client.force_authenticate(teacher)
    assert teacher_client.get("/api/v1/enrollments/").data["count"] == 1

    assert APIClient().get("/api/v1/offerings/").status_code in (401, 403)


def test_history_protected_and_readable(admin_client, world):
    offering = make_offering(world)
    enrollment = services.create_enrollment(offering=offering, student=world["student"])

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
