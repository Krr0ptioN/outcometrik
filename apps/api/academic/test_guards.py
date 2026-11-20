import pytest
from access.models import Role, RoleAssignment, Scope
from django.contrib.auth.models import User
from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from academic.guards import HasScopedCapability, scoped_permission
from academic.router import AcademicRouter, controller, get, post


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


def test_scoped_permission_returns_drf_base_permission_and_composes(auth_world):
    perm_cls = scoped_permission("grades.edit", scope_field="offering")
    assert issubclass(perm_cls, BasePermission)
    assert issubclass(perm_cls, HasScopedCapability)

    # Native DRF `&` composition with IsAuthenticated
    composed = (IsAuthenticated & perm_cls)()
    rf = APIRequestFactory()

    req = rf.post("/dummy/", {"offering": str(auth_world["scope"].pk)}, format="json")
    req.user = auth_world["user"]
    req.data = {"offering": str(auth_world["scope"].pk)}

    class FakeView:
        kwargs = {}

    assert composed.has_permission(req, FakeView()) is True

    req_denied = rf.post("/dummy/", {"offering": str(auth_world["scope"].pk)}, format="json")
    req_denied.user = auth_world["outsider"]
    req_denied.data = {"offering": str(auth_world["scope"].pk)}
    assert composed.has_permission(req_denied, FakeView()) is False


def test_scoped_permission_with_scope_param_and_scope_getter(auth_world):
    rf = APIRequestFactory()

    class FakeView:
        def __init__(self, kwargs):
            self.kwargs = kwargs

    req = rf.post("/dummy/")
    req.user = auth_world["user"]

    param_perm = scoped_permission("grades.edit", scope_param="offering_id")()
    assert param_perm.has_permission(req, FakeView({"offering_id": str(auth_world["scope"].pk)}))
    assert not param_perm.has_permission(req, FakeView({}))

    getter_perm = scoped_permission(
        "grades.edit", scope_getter=lambda view, r, **kw: kw.get("custom_id")
    )()
    assert getter_perm.has_permission(req, FakeView({"custom_id": str(auth_world["scope"].pk)}))
    assert not getter_perm.has_permission(req, FakeView({}))


def test_drf_native_get_permissions_runs_object_permission_once(auth_world):
    """Detail actions enforce HasScopedCapability via DRF's check_object_permissions
    inside get_object(), calling get_object() exactly once per request."""
    router = AcademicRouter()
    get_object_calls = 0

    @controller("sample-drf-perms", router=router)
    class SampleDRFViewSet(viewsets.GenericViewSet):
        permission_classes = [IsAuthenticated]

        def get_object(self):
            nonlocal get_object_calls
            get_object_calls += 1
            obj = auth_world["scope"]
            self.check_object_permissions(self.request, obj)
            return obj

        @post(
            permission_classes=[
                IsAuthenticated,
                scoped_permission("grades.edit", scope_field="offering"),
            ]
        )
        def create(self, request):
            return Response({"ok": True}, status=status.HTTP_201_CREATED)

        @get("{id}", permission_classes=[IsAuthenticated, scoped_permission("grades.edit")])
        def retrieve(self, request, pk=None):
            obj = self.get_object()
            return Response({"id": str(obj.pk)})

    factory = APIRequestFactory()

    # 1. Collection action (create) enforced in DRF check_permissions()
    req_ok = factory.post(
        "/sample-drf-perms/", {"offering": str(auth_world["scope"].pk)}, format="json"
    )
    force_authenticate(req_ok, user=auth_world["user"])
    resp_ok = SampleDRFViewSet.as_view({"post": "create"})(req_ok)
    assert resp_ok.status_code == status.HTTP_201_CREATED

    req_forbidden = factory.post(
        "/sample-drf-perms/", {"offering": str(auth_world["scope"].pk)}, format="json"
    )
    force_authenticate(req_forbidden, user=auth_world["outsider"])
    resp_forbidden = SampleDRFViewSet.as_view({"post": "create"})(req_forbidden)
    assert resp_forbidden.status_code == status.HTTP_403_FORBIDDEN

    # 2. Detail action (retrieve) runs get_object() ONCE and checks has_object_permission
    get_object_calls = 0
    req_detail_ok = factory.get(f"/sample-drf-perms/{auth_world['scope'].pk}/")
    force_authenticate(req_detail_ok, user=auth_world["user"])
    resp_detail_ok = SampleDRFViewSet.as_view({"get": "retrieve"})(
        req_detail_ok, pk=str(auth_world["scope"].pk)
    )
    assert resp_detail_ok.status_code == status.HTTP_200_OK
    assert get_object_calls == 1

    get_object_calls = 0
    req_detail_denied = factory.get(f"/sample-drf-perms/{auth_world['scope'].pk}/")
    force_authenticate(req_detail_denied, user=auth_world["outsider"])
    resp_detail_denied = SampleDRFViewSet.as_view({"get": "retrieve"})(
        req_detail_denied, pk=str(auth_world["scope"].pk)
    )
    assert resp_detail_denied.status_code == status.HTTP_403_FORBIDDEN
    assert get_object_calls == 1
