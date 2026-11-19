import pytest
from access.models import Role, RoleAssignment, Scope
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from academic.guards import guard, require_permission


@pytest.fixture
def auth_world(db):
    user = User.objects.create_user(username="prof_x")
    unauthorized = User.objects.create_user(username="outsider")
    root = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label="ACU")
    program = Scope.objects.create(kind=Scope.Kind.PROGRAM, label="CS", parent=root)
    scope = Scope.objects.create(kind=Scope.Kind.OFFERING, label="CSE101", parent=program)
    role = Role.objects.get(pk="instructor")
    RoleAssignment.objects.create(user=user, role=role, scope=scope)
    return {"user": user, "outsider": unauthorized, "scope": scope}


class DummyController:
    @require_permission("grades.edit")
    def action_with_pk(self, request, pk=None):
        return "success-pk"

    @require_permission("grades.edit", scope_param="offering_id")
    def action_with_scope_param(self, request, offering_id=None):
        return "success-param"

    @guard("grades.edit", scope_getter=lambda self, req, *a, **kw: kw.get("custom_id"))
    def action_with_getter(self, request, custom_id=None):
        return "success-getter"


def test_guard_allows_authorized_actor(auth_world):
    rf = RequestFactory()
    req = rf.post("/dummy/")
    req.user = auth_world["user"]

    controller = DummyController()
    result = controller.action_with_pk(req, pk=str(auth_world["scope"].pk))
    assert result == "success-pk"


def test_guard_denies_unauthorized_actor(auth_world):
    rf = RequestFactory()
    req = rf.post("/dummy/")
    req.user = auth_world["outsider"]

    controller = DummyController()
    with pytest.raises(PermissionDenied):
        controller.action_with_pk(req, pk=str(auth_world["scope"].pk))


def test_guard_with_scope_param(auth_world):
    rf = RequestFactory()
    req = rf.post("/dummy/")
    req.user = auth_world["user"]

    controller = DummyController()
    result = controller.action_with_scope_param(req, offering_id=str(auth_world["scope"].pk))
    assert result == "success-param"


def test_guard_with_scope_getter(auth_world):
    rf = RequestFactory()
    req = rf.post("/dummy/")
    req.user = auth_world["user"]

    controller = DummyController()
    result = controller.action_with_getter(req, custom_id=str(auth_world["scope"].pk))
    assert result == "success-getter"


def test_guard_rejects_missing_scope(auth_world):
    rf = RequestFactory()
    req = rf.post("/dummy/")
    req.user = auth_world["user"]

    controller = DummyController()
    with pytest.raises(PermissionDenied, match="not permitted in this scope"):
        controller.action_with_pk(req)
