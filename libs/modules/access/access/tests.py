import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, models, transaction
from django.http import Http404
from rest_framework.test import APIClient

from .models import AuditEvent, Capability, DirectCapabilityGrant, Role, RoleAssignment, Scope
from .policy import ResourceContext, authorization
from .selectors import visible_resource, visible_resources
from .services import assign, revoke, sensitive_export

pytestmark = pytest.mark.django_db


class ProtectedRecord(models.Model):
    scope = models.ForeignKey(Scope, on_delete=models.PROTECT)
    owner_id = models.IntegerField()
    released = models.BooleanField(default=False)
    published = models.BooleanField(default=False)

    class Meta:
        app_label = "access"
        managed = False


@pytest.fixture(scope="session", autouse=True)
def record_table(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.create_model(ProtectedRecord)
    yield
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.delete_model(ProtectedRecord)


@pytest.fixture
def world(django_user_model):
    users = {
        name: django_user_model.objects.create_user(name)
        for name in ("admin", "coordinator", "instructor", "student", "other", "outsider")
    }
    institution = Scope.objects.create(kind="institution")
    programs = [Scope.objects.create(kind="program", parent=institution) for _ in range(2)]
    offerings = [Scope.objects.create(kind="offering", parent=program) for program in programs]
    for name, role, scope in (
        ("admin", "administrator", institution),
        ("coordinator", "program-coordinator", programs[0]),
        ("instructor", "instructor", offerings[0]),
        ("student", "student", offerings[0]),
    ):
        RoleAssignment.objects.create(user=users[name], role_id=role, scope=scope)
    return users, institution, programs, offerings


def allowed(user, capability, scope, resource=None):
    return authorization.allows(
        principal=user, capability=capability, scope=scope, resource=resource
    )


@pytest.mark.parametrize("name", ["coordinator", "instructor"])
def test_scope_isolation(world, name):
    users, _, _, offerings = world
    assert allowed(users[name], "grades.edit", offerings[0])
    assert not allowed(users[name], "grades.edit", offerings[1])
    with pytest.raises(PermissionDenied):
        authorization.require(principal=users[name], capability="grades.edit", scope=offerings[1])
    assert allowed(users["admin"], "grades.edit", offerings[1])


def test_deny_default_inactive_and_superuser(world):
    users, _, _, offerings = world
    assert not allowed(AnonymousUser(), "grades.view", offerings[0])
    user = users["outsider"]
    user.is_superuser = True
    assert not allowed(user, "grades.view", offerings[0])
    assert not allowed(users["admin"], "unknown", offerings[0])
    users["admin"].is_active = False
    assert not allowed(users["admin"], "grades.view", offerings[0])


@pytest.mark.parametrize(
    "capability,released,published,own,expected",
    [
        ("grades.view", True, False, True, True),
        ("grades.view", False, False, True, False),
        ("grades.view", True, False, False, False),
        ("evidence.view", True, False, False, False),
        ("evidence.view", False, False, True, False),
        ("outcomes.view", False, True, True, True),
        ("outcomes.view", False, False, True, False),
        ("faculty.preview", True, True, True, False),
        ("grades.edit", True, True, True, False),
    ],
)
def test_student_policy_and_selectors(world, capability, released, published, own, expected):
    users, _, _, offerings = world
    student = users["student"]
    owner = student if own else users["other"]
    record = ProtectedRecord.objects.create(
        scope=offerings[0], owner_id=owner.pk, released=released, published=published
    )
    context = ResourceContext(owner.pk, released, published)
    assert allowed(student, capability, offerings[0], context) is expected
    rows = visible_resources(
        ProtectedRecord.objects.all(), principal=student, capability=capability
    )
    assert rows.filter(pk=record.pk).exists() is expected
    if not expected:
        with pytest.raises(Http404):
            visible_resource(
                ProtectedRecord.objects.all(),
                principal=student,
                capability=capability,
                pk=record.pk,
            )
    assert not allowed(student, capability, offerings[1], context)


def test_coordinator_cannot_enumerate_foreign_drafts(world):
    users, _, _, offerings = world
    foreign = ProtectedRecord.objects.create(scope=offerings[1], owner_id=users["other"].pk)
    for name in ("coordinator", "instructor", "student"):
        with pytest.raises(Http404):
            visible_resource(
                ProtectedRecord.objects.all(),
                principal=users[name],
                capability="grades.view",
                pk=foreign.pk,
            )


def test_direct_grants_exact_action_scope_and_immediate_revocation(world):
    users, _, programs, offerings = world
    user = users["outsider"]
    grant = assign(
        actor=users["admin"],
        user=user,
        scope=programs[0],
        capability=Capability.objects.get(pk="grades.edit"),
    )
    assert allowed(user, "grades.edit", programs[0])
    assert not allowed(user, "grades.edit", offerings[0])
    assert not allowed(user, "grades.view", programs[0])
    assert not allowed(user, "grades.edit", programs[1])
    revoke(actor=users["admin"], assignment=grant)
    assert not allowed(user, "grades.edit", programs[0])
    assert list(AuditEvent.objects.values_list("action", flat=True)) == [
        "capability.granted",
        "capability.revoked",
    ]


def test_revoking_direct_grant_preserves_role_and_other_grants(world):
    users, _, _, offerings = world
    for name in ("instructor", "outsider"):
        grant = assign(
            actor=users["admin"],
            user=users[name],
            scope=offerings[0],
            capability=Capability.objects.get(pk="grades.edit"),
        )
        revoke(actor=users["admin"], assignment=grant)
        assert allowed(users[name], "grades.edit", offerings[0]) is (name == "instructor")


def test_role_assignment_audit_validation_and_revocation(world):
    users, _, _, offerings = world
    args = {
        "actor": users["admin"],
        "user": users["outsider"],
        "scope": offerings[0],
        "role": Role.objects.get(pk="instructor"),
    }
    assignment = assign(**args)
    assert assign(**args).pk == assignment.pk
    assert AuditEvent.objects.count() == 1
    assert allowed(users["outsider"], "grades.edit", offerings[0])
    revoke(actor=users["admin"], assignment=assignment)
    revoke(actor=users["admin"], assignment=assignment)
    assert AuditEvent.objects.count() == 2
    assert not allowed(users["outsider"], "grades.edit", offerings[0])
    with pytest.raises(ValidationError):
        assign(**{**args, "role": Role.objects.get(pk="administrator")})
    with pytest.raises(PermissionDenied):
        assign(**{**args, "actor": users["coordinator"]})


def test_audit_and_assignment_rollback_together(world, monkeypatch):
    users, _, _, offerings = world

    def fail(**kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditEvent.objects, "create", fail)
    with pytest.raises(RuntimeError):
        assign(
            actor=users["admin"],
            user=users["outsider"],
            scope=offerings[0],
            role=Role.objects.get(pk="instructor"),
        )
    assert not RoleAssignment.objects.filter(user=users["outsider"]).exists()


def test_sensitive_export_filters_and_audits(world):
    users, _, _, offerings = world
    for scope in offerings:
        ProtectedRecord.objects.create(scope=scope, owner_id=users["other"].pk)
    payload = sensitive_export(
        actor=users["coordinator"],
        scope=offerings[0],
        queryset=ProtectedRecord.objects.all(),
        serialize=lambda rows: list(rows.values("scope_id")),
    )
    assert payload == [{"scope_id": offerings[0].pk}]
    assert AuditEvent.objects.get().metadata == {"count": 1}
    with pytest.raises(PermissionDenied):
        sensitive_export(
            actor=users["instructor"],
            scope=offerings[0],
            queryset=ProtectedRecord.objects.all(),
            serialize=list,
        )
    assert AuditEvent.objects.count() == 1


def test_audit_immutable_in_orm_and_raw_sql(world):
    users, institution, _, _ = world
    event = AuditEvent.objects.create(actor=users["admin"], scope=institution, action="test")
    for mutate in (
        lambda: event.save(),
        lambda: event.delete(),
        lambda: AuditEvent.objects.update(action="forged"),
        lambda: AuditEvent.objects.all().delete(),
    ):
        with pytest.raises(ValidationError):
            mutate()
    for sql in ("UPDATE access_auditevent SET action = 'forged'", "DELETE FROM access_auditevent"):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql)
    event.refresh_from_db()
    assert event.action == "test"


def test_api_auth_validation_denials_and_revocation(world):
    users, _, _, offerings = world
    client = APIClient()
    body = {"user": users["outsider"].pk, "scope": str(offerings[0].pk), "role": "instructor"}
    assert client.post("/api/access/assignments/", body).status_code == 403
    client.force_authenticate(users["student"])
    assert client.post("/api/access/assignments/", body).status_code == 403
    client.force_authenticate(users["admin"])
    assert (
        client.post("/api/access/assignments/", {**body, "role": "administrator"}).status_code
        == 400
    )
    assert (
        client.post("/api/access/assignments/", {**body, "capability": "grades.edit"}).status_code
        == 400
    )
    response = client.post("/api/access/assignments/", body)
    assert response.status_code == 201
    assignment_id = response.data["id"]
    client.force_authenticate(users["coordinator"])
    assert client.delete(f"/api/access/roles/{assignment_id}/").status_code == 404
    client.force_authenticate(users["admin"])
    assert client.delete(f"/api/access/roles/{assignment_id}/").status_code == 204
    assert not allowed(users["outsider"], "grades.edit", offerings[0])


def test_api_assigns_multiple_direct_capabilities_in_one_scoped_request(world):
    users, _, _, offerings = world
    client = APIClient()
    client.force_authenticate(users["admin"])
    response = client.post(
        "/api/access/assignments/",
        {
            "user": users["outsider"].pk,
            "scope": str(offerings[0].pk),
            "capabilities": ["grades.export", "outcomes.view"],
        },
    )
    assert response.status_code == 201, response.data
    assert len(response.data["ids"]) == 2
    grants = DirectCapabilityGrant.objects.filter(user=users["outsider"], revoked_at__isnull=True)
    assert set(grants.values_list("capability_id", flat=True)) == {
        "grades.export",
        "outcomes.view",
    }
    assert (
        AuditEvent.objects.filter(
            actor=users["admin"], subject=users["outsider"], action="capability.granted"
        ).count()
        == 2
    )
    duplicate = client.post(
        "/api/access/assignments/",
        {
            "user": users["outsider"].pk,
            "scope": str(offerings[0].pk),
            "capabilities": ["grades.export", "grades.export"],
        },
    )
    assert duplicate.status_code == 400


def test_session_authentication_enforces_csrf(world):
    users, _, _, offerings = world
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(users["admin"])
    assert (
        client.post(
            "/api/access/assignments/",
            {
                "user": users["outsider"].pk,
                "scope": str(offerings[0].pk),
                "role": "instructor",
            },
        ).status_code
        == 403
    )
    assert RoleAssignment.objects.filter(user=users["outsider"]).count() == 0


def test_scope_validation_and_ancestry_immutable(world):
    _, institution, programs, offerings = world
    with pytest.raises(ValidationError):
        Scope.objects.create(kind="offering", parent=institution)
    offerings[0].parent = programs[1]
    with pytest.raises(ValidationError):
        offerings[0].save()


def test_assignment_api_direct_grant(world):
    users, _, _, offerings = world
    client = APIClient()
    client.force_authenticate(users["admin"])
    response = client.post(
        "/api/access/assignments/",
        {
            "user": users["outsider"].pk,
            "scope": str(offerings[0].pk),
            "capability": "grades.edit",
        },
    )
    assert response.status_code == 201
    assert allowed(users["outsider"], "grades.edit", offerings[0])
    assert not allowed(users["outsider"], "grades.edit", offerings[1])
    assert client.delete(f"/api/access/grants/{response.data['id']}/").status_code == 204
    assert not allowed(users["outsider"], "grades.edit", offerings[0])


def test_visible_object_forbidden_action_returns_403(world):
    from rest_framework.response import Response
    from rest_framework.test import APIRequestFactory, force_authenticate
    from rest_framework.views import APIView

    from .permissions import HasCapability

    users, _, _, offerings = world
    record = ProtectedRecord.objects.create(scope=offerings[0], owner_id=users["other"].pk)

    class ReleaseView(APIView):
        permission_classes = (HasCapability,)
        required_capability = "grades.release"

        def resource_context(self, obj):
            return ResourceContext(obj.owner_id, obj.released, obj.published)

        def post(self, request, pk):
            obj = visible_resource(
                ProtectedRecord.objects.all(),
                principal=request.user,
                capability="grades.view",
                pk=pk,
            )
            self.check_object_permissions(request, obj)
            return Response(status=204)

    request = APIRequestFactory().post("/release/")
    force_authenticate(request, users["instructor"])
    assert ReleaseView.as_view()(request, pk=record.pk).status_code == 403
    request = APIRequestFactory().post("/release/")
    force_authenticate(request, users["student"])
    assert ReleaseView.as_view()(request, pk=record.pk).status_code == 404


def test_password_session_and_csrf_success(world):
    from django.middleware.csrf import get_token
    from django.test import RequestFactory

    users, _, _, offerings = world
    user = users["admin"]
    user.set_password("auth01-test-password")
    user.save()
    client = APIClient(enforce_csrf_checks=True)
    assert client.login(username=user.username, password="auth01-test-password")
    csrf_request = RequestFactory().get("/")
    token = get_token(csrf_request)
    client.cookies["csrftoken"] = csrf_request.META["CSRF_COOKIE"]
    response = client.post(
        "/api/access/assignments/",
        {
            "user": users["outsider"].pk,
            "scope": str(offerings[0].pk),
            "role": "instructor",
        },
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 201


def test_bootstrap_is_audited_and_one_time(django_user_model):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    user = django_user_model.objects.create_user("first-admin")
    call_command("bootstrap_access", user.username)
    assert AuditEvent.objects.get().metadata["bootstrap"] is True
    assert RoleAssignment.objects.get(user=user).role_id == "administrator"
    with pytest.raises(CommandError):
        call_command("bootstrap_access", user.username)
