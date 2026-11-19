import pytest
from access.models import Role, RoleAssignment, Scope
from access.policy import AuthorizationService
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.controllers.outcomes import (
    ProgramOutcomeController,
    ProgramOutcomeSetController,
)
from academic.models import Department, Institution, Program, ProgramOutcomeSet
from academic.services.outcomes import (
    ProgramOutcomeService,
    ProgramOutcomeSetService,
)


@pytest.fixture
def outcome_world(db):
    user_model = get_user_model()
    admin = user_model.objects.create_user("out_admin")
    guest = user_model.objects.create_user("out_guest")

    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="Outcome University")
    RoleAssignment.objects.create(user=admin, role=Role.objects.get(pk="administrator"), scope=root)

    inst = Institution.objects.create(pk=root.pk, code="OU", name="Outcome University")
    dept = Department.objects.create(institution=inst, code="CS", name="Computer Science")
    program = Program.objects.create(
        department=dept,
        code="CS-BS",
        title="B.S. in Computer Science",
        status=Program.Status.ACTIVE,
    )

    po_set = ProgramOutcomeSet.objects.create(
        program=program,
        version=1,
        source_reference="docs/ref",
        status=ProgramOutcomeSet.Status.DRAFT,
    )

    return {
        "admin": admin,
        "guest": guest,
        "inst": inst,
        "dept": dept,
        "program": program,
        "po_set": po_set,
    }


def test_outcome_services_registered_in_wireup():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        pos_svc = scoped.get(ProgramOutcomeSetService)
        assert isinstance(pos_svc, ProgramOutcomeSetService)
        assert isinstance(pos_svc.auth_service, AuthorizationService)

        po_svc = scoped.get(ProgramOutcomeService)
        assert isinstance(po_svc, ProgramOutcomeService)
        assert isinstance(po_svc.auth_service, AuthorizationService)


def test_outcome_services_constructor_injection_and_scoping(outcome_world):
    auth_service = AuthorizationService()
    svc = ProgramOutcomeSetService(auth_service=auth_service)

    admin_qs = svc.get_queryset(actor=outcome_world["admin"])
    assert admin_qs.filter(pk=outcome_world["po_set"].pk).exists()

    guest_qs = svc.get_queryset(actor=outcome_world["guest"])
    assert not guest_qs.filter(pk=outcome_world["po_set"].pk).exists()


def test_outcome_mutations_and_immutability(outcome_world):
    auth_service = AuthorizationService()
    pos_svc = ProgramOutcomeSetService(auth_service=auth_service)
    po_svc = ProgramOutcomeService(auth_service=auth_service)

    # Add outcome
    outcome = po_svc.create(
        outcome_set=outcome_world["po_set"],
        code="PO1",
        label="Problem Solving",
        description="Solve CS problems",
        source_url="docs/ref#1",
        order=1,
    )
    assert outcome.pk is not None
    assert outcome.ordering == 1

    # Immutability of outcome_set
    other_set = pos_svc.create(
        program=outcome_world["program"],
        source_reference="docs/ref2",
    )
    with pytest.raises(ValidationError):
        po_svc.update(instance=outcome, outcome_set=other_set)


def test_outcomes_controllers_constructor_injection():
    pos_ctrl = ProgramOutcomeSetController()
    assert isinstance(pos_ctrl.service, ProgramOutcomeSetService)
    assert isinstance(pos_ctrl.outcome_service, ProgramOutcomeService)

    po_ctrl = ProgramOutcomeController()
    assert isinstance(po_ctrl.service, ProgramOutcomeService)
