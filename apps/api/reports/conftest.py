from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from access.models import DirectCapabilityGrant, RoleAssignment, Scope
from django.contrib.auth import get_user_model

from .domain import (
    Evidence,
    EvidenceInput,
    OutcomeRow,
    Report,
    ReportHeader,
    ResultState,
)

User = get_user_model()
NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def make_report(kind, scope_ids, *, publication_id=None, rows=None, title="Engineering knowledge"):
    header = ReportHeader(
        publication_id=publication_id or uuid4(),
        run_id=uuid4(),
        program="Computer Engineering",
        term="2026 Fall",
        po_set_version="PO-set v2",
        policy_version="policy-2026.1",
        scope_label="Computer Engineering (program)",
        population="Students with at least one released grade",
        sample_size=2,
        coverage="2 of 3 students measured",
        published_at=datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
    )
    evidence = Evidence(
        formula="sum(weight x LO) / sum(weight)",
        numerator=Decimal("254.857142857"),
        denominator=Decimal(3),
        inputs=(
            EvidenceInput("LO1", "syllabus-r3", Decimal(2), Decimal(86), ResultState.MEASURED),
            EvidenceInput(
                "LO2", "syllabus-r3", Decimal(1), Decimal("82.857142857"), ResultState.MEASURED
            ),
        ),
    )
    default_rows = (
        OutcomeRow(
            "PO1", title, Decimal("84.952380952"), ResultState.MEASURED, 2, 3, evidence=evidence
        ),
        OutcomeRow("PO2", "Problem analysis", Decimal(0), ResultState.MEASURED, 1, 3),
        OutcomeRow("PO3", "Design", None, ResultState.NOT_ASSESSED, 0, 3),
    )
    return Report(kind, header, rows or default_rows, tuple(scope_ids))


class FakeReader:
    """Stands in for the future publication reader; returns published data only."""

    def __init__(self):
        self.students = {}  # (publication_id, student_pk) -> Report
        self.cohorts = {}  # (publication_id, program_id) -> Report

    def student_report(self, *, publication_id, student):
        return self.students.get((publication_id, student.pk))

    def cohort_report(self, *, publication_id, program_id):
        return self.cohorts.get((publication_id, program_id))


@pytest.fixture
def world(db):
    inst = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Acibadem")
    program_a = Scope.objects.create(kind=Scope.Kind.PROGRAM, label="CENG", parent=inst)
    program_b = Scope.objects.create(kind=Scope.Kind.PROGRAM, label="EEE", parent=inst)
    offering = Scope.objects.create(kind=Scope.Kind.OFFERING, label="CSE311-01", parent=program_a)

    def user(name, role=None, scope=None):
        account = User.objects.create_user(name, password="x", first_name=name.title())
        if role:
            RoleAssignment.objects.create(user=account, scope=scope, role_id=role)
        return account

    people = {
        "admin": user("admin", "administrator", inst),
        "coord_a": user("coord_a", "program-coordinator", program_a),
        "coord_b": user("coord_b", "program-coordinator", program_b),
        "instructor": user("instructor", "instructor", offering),
        "student": user("student", "student", offering),
        "other_student": user("other_student", "student", offering),
        "outsider": user("outsider"),
    }
    # View-only faculty: may see outcomes in the program but not the evidence behind them.
    viewer = user("viewer")
    DirectCapabilityGrant.objects.create(
        user=viewer, scope=program_a, capability_id="outcomes.view"
    )
    people["viewer"] = viewer
    return {
        **people,
        "inst": inst,
        "program_a": program_a,
        "program_b": program_b,
        "offering": offering,
    }


@pytest.fixture
def published(world):
    """One student report and one cohort report, both published for program A."""
    reader = FakeReader()
    publication_id = uuid4()
    student_report = make_report("student", [world["offering"].pk], publication_id=publication_id)
    cohort_report = make_report("cohort", [world["program_a"].pk], publication_id=publication_id)
    reader.students[(publication_id, world["student"].pk)] = student_report
    reader.cohorts[(publication_id, world["program_a"].pk)] = cohort_report
    return {"reader": reader, "publication_id": publication_id}


def uuid_of(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
