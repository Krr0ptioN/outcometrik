import datetime as dt

import pytest
from access.models import RoleAssignment
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.urls import reverse
from rest_framework.test import APIClient

from academic.models import (
    Department,
    Institution,
    Program,
    ProgramOutcome,
    ProgramOutcomeSet,
)
from academic.services import ProgramOutcomeService, ProgramOutcomeSetService

pytestmark = pytest.mark.django_db
User = get_user_model()
EFFECTIVE = dt.date(2026, 9, 1)


@pytest.fixture
def world():
    inst = Institution.objects.create(code="ACU", name="Acibadem")
    admin = User.objects.create_user("admin", password="x")
    RoleAssignment.objects.create(user=admin, scope_id=inst.pk, role_id="administrator")
    outsider = User.objects.create_user("outsider", password="x")
    dept = Department.objects.create(institution=inst, code="CSE", name="Computer Eng")
    program = Program.objects.create(department=dept, code="CENG", title="Computer Eng")
    return {"admin": admin, "outsider": outsider, "program": program}


def add_outcomes(outcome_set, count=11):
    for i in range(1, count + 1):
        ProgramOutcome.objects.create(
            outcome_set=outcome_set,
            code=f"PO{i}",
            label=f"Label {i}",
            description=f"Description {i}",
            source_url="docs/ref#po",
            ordering=i,
        )


def make_draft(world, count=11):
    outcome_set = ProgramOutcomeSetService(actor=world["admin"]).create(
        program=world["program"], source_reference="docs/ref"
    )
    add_outcomes(outcome_set, count)
    return outcome_set


def test_create_draft_assigns_incrementing_version(world):
    first = make_draft(world)
    ProgramOutcomeSetService(actor=world["admin"]).activate(
        instance=first, effective_date=EFFECTIVE
    )
    second = ProgramOutcomeSetService(actor=world["admin"]).create(
        program=world["program"], source_reference="docs/ref"
    )
    assert (first.version, second.version) == (1, 2)
    assert second.status == ProgramOutcomeSet.Status.DRAFT


def test_draft_rejects_duplicate_code_and_ordering(world):
    outcome_set = make_draft(world, count=2)
    service = ProgramOutcomeService(actor=world["admin"])
    base = {"outcome_set": outcome_set, "label": "x", "description": "x", "source_url": "x"}
    with pytest.raises(ValidationError):
        service.create(code="PO1", ordering=3, **base)
    with pytest.raises(ValidationError):
        service.create(code="PO3", ordering=1, **base)


def test_draft_rejects_invalid_ordering(world):
    outcome_set = make_draft(world, count=1)
    with pytest.raises(ValidationError):
        ProgramOutcomeService(actor=world["admin"]).create(
            outcome_set=outcome_set,
            code="PO9",
            label="x",
            description="x",
            source_url="x",
            ordering=0,
        )


def test_activation_rejects_missing_description(world):
    outcome_set = make_draft(world, count=3)
    ProgramOutcome.objects.filter(outcome_set=outcome_set, code="PO2").update(description=" ")
    with pytest.raises(ValidationError):
        ProgramOutcomeSetService(actor=world["admin"]).activate(
            instance=outcome_set, effective_date=EFFECTIVE
        )


def test_activation_rejects_missing_source_url_and_reference(world):
    outcome_set = make_draft(world, count=2)
    ProgramOutcome.objects.filter(outcome_set=outcome_set, code="PO1").update(source_url="")
    with pytest.raises(ValidationError):
        ProgramOutcomeSetService(actor=world["admin"]).activate(
            instance=outcome_set, effective_date=EFFECTIVE
        )
    ProgramOutcome.objects.filter(outcome_set=outcome_set, code="PO1").update(source_url="x")
    ProgramOutcomeSet.objects.filter(pk=outcome_set.pk).update(source_reference="")
    with pytest.raises(ValidationError):
        ProgramOutcomeSetService(actor=world["admin"]).activate(
            instance=ProgramOutcomeSet.objects.get(pk=outcome_set.pk), effective_date=EFFECTIVE
        )


def test_activation_rejects_ordering_gap(world):
    outcome_set = make_draft(world, count=3)
    ProgramOutcome.objects.filter(outcome_set=outcome_set, code="PO3").update(ordering=5)
    with pytest.raises(ValidationError):
        ProgramOutcomeSetService(actor=world["admin"]).activate(
            instance=outcome_set, effective_date=EFFECTIVE
        )


def test_activation_requires_effective_date(world):
    outcome_set = make_draft(world)
    with pytest.raises(ValidationError):
        ProgramOutcomeSetService(actor=world["admin"]).activate(
            instance=outcome_set, effective_date=None
        )


def test_activation_records_actor_and_time(world):
    outcome_set = make_draft(world)
    ProgramOutcomeSetService(actor=world["admin"]).activate(
        instance=outcome_set, effective_date=EFFECTIVE
    )
    outcome_set.refresh_from_db()
    assert outcome_set.status == ProgramOutcomeSet.Status.ACTIVE
    assert outcome_set.activated_by == world["admin"]
    assert outcome_set.activated_at is not None
    assert [o.code for o in outcome_set.outcomes.all()] == [f"PO{i}" for i in range(1, 12)]


def test_active_set_is_immutable(world):
    outcome_set = make_draft(world)
    ProgramOutcomeSetService(actor=world["admin"]).activate(
        instance=outcome_set, effective_date=EFFECTIVE
    )
    outcome_set.refresh_from_db()

    outcome_set.source_reference = "changed"
    with pytest.raises(ValidationError):
        outcome_set.save()

    outcome = outcome_set.outcomes.first()
    outcome.label = "changed"
    with pytest.raises(ValidationError):
        outcome.save()

    with pytest.raises(ValidationError):
        ProgramOutcomeSetService(actor=world["admin"]).update(
            instance=outcome_set, source_reference="changed"
        )
    with pytest.raises(ValidationError):
        ProgramOutcomeService(actor=world["admin"]).update(instance=outcome, label="changed")
    with pytest.raises(ValidationError):
        ProgramOutcomeService(actor=world["admin"]).create(
            outcome_set=outcome_set,
            code="PO12",
            label="x",
            description="x",
            source_url="x",
            ordering=12,
        )
    with pytest.raises(ProtectedError):
        outcome.delete()


def test_new_version_leaves_old_unchanged(world):
    first = make_draft(world)
    ProgramOutcomeSetService(actor=world["admin"]).activate(
        instance=first, effective_date=EFFECTIVE
    )
    second = make_draft(world)
    ProgramOutcome.objects.filter(outcome_set=second, code="PO1").update(label="Reworded")
    ProgramOutcomeSetService(actor=world["admin"]).activate(
        instance=second, effective_date=dt.date(2027, 9, 1)
    )

    first.refresh_from_db()
    assert first.outcomes.get(code="PO1").label == "Label 1"
    assert first.effective_date == EFFECTIVE
    assert second.version == 2


def test_new_active_set_must_start_after_current(world):
    first = make_draft(world)
    ProgramOutcomeSetService(actor=world["admin"]).activate(
        instance=first, effective_date=EFFECTIVE
    )
    second = make_draft(world)
    with pytest.raises(ValidationError):
        ProgramOutcomeSetService(actor=world["admin"]).activate(
            instance=second, effective_date=EFFECTIVE
        )


def test_denied_scope_for_user_without_capability(world):
    outsider = world["outsider"]
    client = APIClient()
    client.force_authenticate(outsider)

    # Outcome set create denied
    r_create = client.post(
        reverse("program-outcome-set-list"),
        {"program": str(world["program"].pk), "source_reference": "x"},
        format="json",
    )
    assert r_create.status_code == 403

    draft = make_draft(world)
    # Outcome set activate denied (returns 404 because outsider cannot view the outcome set)
    r_act = client.post(
        reverse("program-outcome-set-activate", args=[draft.pk]),
        {"effective_date": str(EFFECTIVE)},
        format="json",
    )
    assert r_act.status_code in (403, 404)

    # Outcome create denied
    r_out = client.post(
        reverse("program-outcome-list"),
        {
            "outcome_set": str(draft.pk),
            "code": "PO99",
            "label": "x",
            "description": "x",
            "source_url": "x",
            "ordering": 99,
        },
        format="json",
    )
    assert r_out.status_code == 403
    assert not ProgramOutcomeSetService(actor=outsider).get_queryset().exists()


def test_api_create_add_activate_and_denied(world):
    client = APIClient()
    client.force_authenticate(world["admin"])
    created = client.post(
        reverse("program-outcome-set-list"),
        {"program": str(world["program"].pk), "source_reference": "docs/ref"},
        format="json",
    )
    assert created.status_code == 201
    set_id = created.json()["id"]

    outcome = client.post(
        reverse("program-outcome-list"),
        {
            "outcome_set": set_id,
            "code": "PO1",
            "label": "L",
            "description": "D",
            "source_url": "u",
            "ordering": 1,
        },
        format="json",
    )
    assert outcome.status_code == 201

    activated = client.post(
        reverse("program-outcome-set-activate", args=[set_id]),
        {"effective_date": "2026-09-01"},
        format="json",
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    edit = client.patch(
        reverse("program-outcome-detail", args=[outcome.json()["id"]]),
        {"label": "Changed"},
        format="json",
    )
    assert edit.status_code == 400

    outsider = APIClient()
    outsider.force_authenticate(world["outsider"])
    denied = outsider.post(
        reverse("program-outcome-set-list"),
        {"program": str(world["program"].pk), "source_reference": "x"},
        format="json",
    )
    assert denied.status_code == 403
