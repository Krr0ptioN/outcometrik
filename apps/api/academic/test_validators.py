import datetime as dt

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from academic.models import (
    AcademicTerm,
    Course,
    CourseOffering,
    Department,
    Institution,
    LearningOutcome,
    Program,
    ProgramCourse,
    ProgramOutcome,
    ProgramOutcomeSet,
    Syllabus,
    SyllabusAssessment,
)
from academic.services import ProgramOutcomeSetValidator, SyllabusValidator

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def base_world():
    inst = Institution.objects.create(code="ACU", name="Acibadem")
    admin = User.objects.create_user("admin", password="x")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Eng")
    program = Program.objects.create(department=dept, code="CENG", title="Computer Eng")
    term = AcademicTerm.objects.create(
        institution=inst,
        year=2026,
        season="fall",
        starts_at=dt.date(2026, 9, 1),
        ends_at=dt.date(2027, 1, 15),
    )
    course = Course.objects.create(
        home_department=dept, code="CSE101", title="Intro to CS", ects=6, credits=3
    )
    ProgramCourse.objects.create(
        program=program,
        course=course,
        effective_from=dt.date(2026, 1, 1),
        status="approved",
    )
    offering = CourseOffering.objects.create(
        program=program, course=course, term=term, section="01"
    )
    return {
        "institution": inst,
        "admin": admin,
        "department": dept,
        "program": program,
        "term": term,
        "course": course,
        "offering": offering,
    }


# =====================================================================
# ProgramOutcomeSetValidator Tests
# =====================================================================


def test_outcome_set_validator_mutation_on_active_set_raises(base_world):
    po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.ACTIVE,
        source_reference="docs/ref",
        effective_date=dt.date(2026, 1, 1),
        activated_at=timezone.now(),
        activated_by=base_world["admin"],
    )
    with pytest.raises(ValidationError, match="Outcomes of an active set are immutable"):
        ProgramOutcomeSetValidator.validate_mutation(po_set)


def test_outcome_set_validator_mutation_on_draft_passes(base_world):
    po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
    )
    # Should not raise
    ProgramOutcomeSetValidator.validate_mutation(po_set)


def test_outcome_set_validator_set_update_on_active_set_raises(base_world):
    po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.ACTIVE,
        source_reference="docs/ref",
        effective_date=dt.date(2026, 1, 1),
        activated_at=timezone.now(),
        activated_by=base_world["admin"],
    )
    with pytest.raises(ValidationError, match="An active set is immutable"):
        ProgramOutcomeSetValidator.validate_set_update(po_set, "source_reference")


def test_outcome_set_validator_activation_empty_outcomes_raises(base_world):
    po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="docs/ref",
    )
    with pytest.raises(ValidationError, match="A set needs at least one outcome"):
        ProgramOutcomeSetValidator.validate_activation(po_set, dt.date(2026, 9, 1))


def test_outcome_set_validator_activation_missing_source_raises(base_world):
    po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="",
    )
    ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO1",
        label="PO 1",
        description="PO 1 desc",
        source_url="docs/po1",
        ordering=1,
    )
    with pytest.raises(ValidationError, match="source_reference"):
        ProgramOutcomeSetValidator.validate_activation(po_set, dt.date(2026, 9, 1))


def test_outcome_set_validator_activation_missing_description_raises(base_world):
    po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="docs/ref",
    )
    ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO1",
        label="PO 1",
        description="",
        source_url="docs/po1",
        ordering=1,
    )
    with pytest.raises(ValidationError, match="description is required"):
        ProgramOutcomeSetValidator.validate_activation(po_set, dt.date(2026, 9, 1))


def test_outcome_set_validator_activation_ordering_gap_raises(base_world):
    po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
        source_reference="docs/ref",
    )
    ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO1",
        label="PO 1",
        description="PO 1 desc",
        source_url="docs/po1",
        ordering=1,
    )
    ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO2",
        label="PO 2",
        description="PO 2 desc",
        source_url="docs/po2",
        ordering=3,  # Gap: missing ordering 2
    )
    with pytest.raises(ValidationError, match="Ordering must be 1..N with no gaps"):
        ProgramOutcomeSetValidator.validate_activation(po_set, dt.date(2026, 9, 1))


def test_outcome_set_validator_sibling_uniqueness(base_world):
    po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.DRAFT,
    )
    ProgramOutcome.objects.create(
        outcome_set=po_set,
        code="PO1",
        label="PO 1",
        description="PO 1 desc",
        source_url="docs/po1",
        ordering=1,
    )

    with pytest.raises(ValidationError, match="Must be unique within the set"):
        ProgramOutcomeSetValidator.validate_mutation(po_set, data={"code": "PO1", "ordering": 2})

    with pytest.raises(ValidationError, match="Must be unique within the set"):
        ProgramOutcomeSetValidator.validate_mutation(po_set, data={"code": "PO2", "ordering": 1})


# =====================================================================
# SyllabusValidator Tests
# =====================================================================


def test_syllabus_validator_editable_rejects_locked(base_world):
    syllabus = Syllabus.objects.create(
        offering=base_world["offering"],
        version=1,
        status=Syllabus.Status.APPROVED,
        po_set_version=1,
        approved_by=base_world["admin"],
        approved_at=timezone.now(),
    )
    with pytest.raises(ValidationError, match="This syllabus version is locked"):
        SyllabusValidator.validate_editable(syllabus)


def test_syllabus_validator_creation_rejects_if_draft_or_approved_exists(base_world):
    offering = base_world["offering"]
    Syllabus.objects.create(
        offering=offering,
        version=1,
        status=Syllabus.Status.DRAFT,
    )
    with pytest.raises(ValidationError, match="already exists for this offering"):
        SyllabusValidator.validate_creation(offering)


def test_syllabus_validator_approval_requires_los_and_assessments(base_world):
    syllabus = Syllabus.objects.create(
        offering=base_world["offering"],
        version=1,
        status=Syllabus.Status.DRAFT,
        po_set_version=1,
    )
    active_po_set = ProgramOutcomeSet.objects.create(
        program=base_world["program"],
        version=1,
        status=ProgramOutcomeSet.Status.ACTIVE,
        source_reference="docs/ref",
        effective_date=dt.date(2026, 1, 1),
        activated_at=timezone.now(),
        activated_by=base_world["admin"],
    )
    # No LO or assessments yet
    with pytest.raises(ValidationError, match="needs at least one LO and one assessment"):
        SyllabusValidator.validate_approval(syllabus, active_po_set)

    # Add LO only
    LearningOutcome.objects.create(syllabus=syllabus, code="LO1", description="desc", order=1)
    with pytest.raises(ValidationError, match="needs at least one LO and one assessment"):
        SyllabusValidator.validate_approval(syllabus, active_po_set)

    # Add assessment
    SyllabusAssessment.objects.create(
        syllabus=syllabus, code="MT", kind="exam", order=1, max_points=100
    )
    # Active PO set mismatch
    active_po_set.version = 2
    with pytest.raises(ValidationError, match="bind to the program's active PO-set version"):
        SyllabusValidator.validate_approval(syllabus, active_po_set)

    # Valid
    active_po_set.version = 1
    # Should not raise
    SyllabusValidator.validate_approval(syllabus, active_po_set)


def test_syllabus_validator_revision_rules(base_world):
    offering = base_world["offering"]
    draft = Syllabus.objects.create(
        offering=offering,
        version=1,
        status=Syllabus.Status.DRAFT,
    )
    with pytest.raises(ValidationError, match="Only an approved syllabus version can be revised"):
        SyllabusValidator.validate_revision(draft, offering)

    # Make it approved with valid metadata
    draft.status = Syllabus.Status.APPROVED
    draft.po_set_version = 1
    draft.approved_by = base_world["admin"]
    draft.approved_at = timezone.now()
    draft.save()

    # If offering also has a draft
    Syllabus.objects.create(
        offering=offering,
        version=2,
        status=Syllabus.Status.DRAFT,
    )
    with pytest.raises(ValidationError, match="A draft revision already exists"):
        SyllabusValidator.validate_revision(draft, offering)


def test_syllabus_validator_active_po_set_binding(base_world):
    syllabus = Syllabus.objects.create(
        offering=base_world["offering"],
        version=1,
        status=Syllabus.Status.DRAFT,
    )
    with pytest.raises(ValidationError, match="No active PO-set exists"):
        SyllabusValidator.validate_active_po_set_binding(syllabus, None)


def test_syllabus_validator_draft_removal(base_world):
    syllabus = Syllabus.objects.create(
        offering=base_world["offering"],
        version=1,
        status=Syllabus.Status.DRAFT,
    )
    LearningOutcome.objects.create(syllabus=syllabus, code="LO1", description="d", order=1)
    with pytest.raises(ValidationError, match="holds configuration; revise instead of removing"):
        SyllabusValidator.validate_draft_removal(syllabus)


def test_syllabus_validator_assessment_points():
    with pytest.raises(ValidationError, match="Maximum points must be greater than zero"):
        SyllabusValidator.validate_assessment_points(0)

    with pytest.raises(ValidationError, match="Maximum points must be greater than zero"):
        SyllabusValidator.validate_assessment_points(-5)

    # Valid values
    SyllabusValidator.validate_assessment_points(10)
    SyllabusValidator.validate_assessment_points(None)
