import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils.crypto import get_random_string
from rest_framework.test import APIClient

from .models import AuditEvent, RoleAssignment, Scope

pytestmark = pytest.mark.django_db
TEST_PASSWORD = get_random_string(48)


@pytest.fixture(autouse=True)
def reset_throttle():
    cache.clear()


@pytest.fixture
def institution():
    admin = get_user_model().objects.create_user("operator", password=TEST_PASSWORD)
    root = Scope.objects.create(kind="institution", label="Northbridge University")
    program = Scope.objects.create(kind="program", label="Engineering", parent=root)
    offering = Scope.objects.create(kind="offering", label="CSE 301", parent=program)
    RoleAssignment.objects.create(user=admin, role_id="administrator", scope=root)
    client = APIClient()
    client.force_login(admin)
    return client, admin, root, program, offering


def account_body(offering, **overrides):
    return {
        "username": "new.student",
        "email": "student@example.edu",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "password": TEST_PASSWORD,
        "role": "student",
        "scope": str(offering.pk),
        **overrides,
    }


@pytest.mark.parametrize("role", ["student", "instructor"])
def test_create_account_with_hashed_password_and_scoped_role(institution, role):
    client, _, root, _, offering = institution
    response = client.post("/api/access/accounts/", account_body(offering, role=role))
    assert response.status_code == 201, response.data
    user = get_user_model().objects.get(pk=response.data["id"])
    assert user.check_password(TEST_PASSWORD)
    assert "password" not in response.data
    assert RoleAssignment.objects.get(user=user).scope == offering
    assert RoleAssignment.objects.get(user=user).role_id == role
    assert set(AuditEvent.objects.values_list("action", flat=True)) == {
        "account.created",
        "role.assigned",
    }
    dashboard = client.get("/api/access/dashboard/", {"scope": str(root.pk)})
    assert dashboard.status_code == 200
    assert dashboard.data["counts"]["users"] == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"password": "password"},
        {"username": "spaces not valid"},
        {"email": "invalid"},
        {"role": "administrator"},
        {"role": "unknown"},
    ],
)
def test_invalid_account_does_not_leave_user_or_audit(institution, changes):
    client, _, _, _, offering = institution
    response = client.post("/api/access/accounts/", account_body(offering, **changes))
    assert response.status_code == 400
    assert get_user_model().objects.count() == 1
    assert not AuditEvent.objects.exists()


def test_duplicate_username_safe_and_no_extra_assignment(institution):
    client, _, _, _, offering = institution
    assert client.post("/api/access/accounts/", account_body(offering)).status_code == 201
    assert client.post("/api/access/accounts/", account_body(offering)).status_code == 400
    assert get_user_model().objects.count() == 2
    assert AuditEvent.objects.count() == 2


def test_account_creation_audit_failure_rolls_back(institution, monkeypatch):
    client, _, _, _, offering = institution

    def fail(**kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(AuditEvent.objects, "create", fail)
    with pytest.raises(RuntimeError):
        client.post("/api/access/accounts/", account_body(offering))
    assert get_user_model().objects.count() == 1


def test_institution_dashboard_isolates_accounts_assignments_and_audit(institution):
    client, admin, root, _, offering = institution
    other_root = Scope.objects.create(kind="institution", label="Another institution")
    other_admin = get_user_model().objects.create_user("other-admin")
    RoleAssignment.objects.create(user=other_admin, role_id="administrator", scope=other_root)
    # A shared person must not reveal their role in the other institution.
    RoleAssignment.objects.create(user=admin, role_id="administrator", scope=other_root)
    AuditEvent.objects.create(actor=other_admin, scope=other_root, action="private.event")
    response = client.get("/api/access/dashboard/", {"scope": str(root.pk)})
    assert response.status_code == 200
    assert [u["username"] for u in response.data["users"]] == ["operator"]
    assert len(response.data["users"][0]["roles"]) == 1
    assert not response.data["audit"]
    assert other_root.pk not in {s["id"] for s in response.data["scopes"]}
    client.force_login(other_admin)
    assert client.get("/api/access/dashboard/", {"scope": str(root.pk)}).status_code == 403
    assert client.post("/api/access/accounts/", account_body(offering)).status_code == 403
    assert not get_user_model().objects.filter(username="new.student").exists()


def test_only_institution_administrators_can_use_dashboard(institution):
    client, _, root, program, offering = institution
    user = get_user_model().objects.create_user("faculty")
    RoleAssignment.objects.create(user=user, role_id="instructor", scope=offering)
    client.force_login(user)
    assert client.get("/api/access/dashboard/", {"scope": str(root.pk)}).status_code == 403
    assert client.post("/api/access/accounts/", account_body(offering)).status_code == 403
    assert client.get("/api/access/dashboard/", {"scope": str(program.pk)}).status_code == 400
    client.logout()
    assert client.get("/api/access/dashboard/", {"scope": str(root.pk)}).status_code == 403


def test_dashboard_search_and_pagination(institution):
    client, _, root, _, offering = institution
    for index in range(22):
        user = get_user_model().objects.create_user(
            f"learner{index}", email=f"l{index}@example.edu"
        )
        RoleAssignment.objects.create(user=user, role_id="student", scope=offering)
    response = client.get("/api/access/dashboard/", {"scope": str(root.pk)})
    assert response.data["total"] == 23
    assert len(response.data["users"]) == 20
    response = client.get("/api/access/dashboard/", {"scope": str(root.pk), "page": 2})
    assert len(response.data["users"]) == 3
    response = client.get("/api/access/dashboard/", {"scope": str(root.pk), "search": "l21@"})
    assert [u["username"] for u in response.data["users"]] == ["learner21"]
    assert (
        client.get("/api/access/dashboard/", {"scope": str(root.pk), "page": 0}).status_code == 400
    )


def test_last_administrator_cannot_be_revoked(institution):
    client, admin, root, _, _ = institution
    assignment = RoleAssignment.objects.get(user=admin, scope=root)
    response = client.delete(f"/api/access/roles/{assignment.pk}/")
    assert response.status_code == 400
    assignment.refresh_from_db()
    assert assignment.revoked_at is None
    assert not AuditEvent.objects.exists()


def test_real_login_csrf_rotation_and_logout(institution):
    _, _, root, _, _ = institution
    client = APIClient(enforce_csrf_checks=True)
    assert (
        client.post(
            "/api/auth/login/", {"username": "operator", "password": TEST_PASSWORD}
        ).status_code
        == 403
    )
    response = client.get("/api/auth/session/")
    assert response.data == {"user": None, "scopes": [], "roles": []}
    token = client.cookies["csrftoken"].value
    response = client.post(
        "/api/auth/login/",
        {"username": "operator", "password": TEST_PASSWORD},
        HTTP_X_CSRFTOKEN=token,
        HTTP_ORIGIN="http://localhost:3000",
    )
    assert response.status_code == 200
    assert response.data["user"]["username"] == "operator"
    assert response["Cache-Control"] == "no-store"
    assert any(role["role"] == "administrator" for role in response.data["roles"])
    assert "password" not in response.data["user"]
    assert any(s["id"] == str(root.pk) for s in response.data["scopes"])
    assert client.get("/api/access/dashboard/", {"scope": str(root.pk)}).status_code == 200
    assert client.post("/api/auth/logout/").status_code == 403
    response = client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
    assert response.status_code == 200
    assert client.get("/api/auth/session/").data["user"] is None


def test_login_invalid_inactive_and_throttled(institution):
    _, admin, _, _, _ = institution
    client = APIClient(enforce_csrf_checks=True)
    client.get("/api/auth/session/")
    token = client.cookies["csrftoken"].value
    for username in ("operator", "missing"):
        response = client.post(
            "/api/auth/login/", {"username": username, "password": "wrong"}, HTTP_X_CSRFTOKEN=token
        )
        assert response.status_code == 400
        assert response.data == {"detail": "Invalid username or password."}
    admin.is_active = False
    admin.save()
    assert (
        client.post(
            "/api/auth/login/",
            {"username": "operator", "password": TEST_PASSWORD},
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        == 400
    )
    for _ in range(7):
        client.post(
            "/api/auth/login/", {"username": "missing", "password": "wrong"}, HTTP_X_CSRFTOKEN=token
        )
    assert (
        client.post(
            "/api/auth/login/", {"username": "missing", "password": "wrong"}, HTTP_X_CSRFTOKEN=token
        ).status_code
        == 429
    )


def test_membership_survives_last_role_revocation(institution):
    client, _, root, _, offering = institution
    response = client.post("/api/access/accounts/", account_body(offering))
    user_id = response.data["id"]
    assignment = RoleAssignment.objects.get(user_id=user_id)
    assert client.delete(f"/api/access/roles/{assignment.pk}/").status_code == 204
    response = client.get("/api/access/dashboard/", {"scope": str(root.pk)})
    user = next(u for u in response.data["users"] if u["id"] == user_id)
    assert user["roles"] == []
    assert user["grants"] == []
    assert (
        client.post(
            "/api/access/assignments/",
            {
                "user": user_id,
                "scope": str(offering.pk),
                "role": "student",
            },
        ).status_code
        == 201
    )


def test_account_payload_cannot_set_global_privileges(institution):
    client, _, _, _, offering = institution
    response = client.post(
        "/api/access/accounts/", account_body(offering, is_staff=True, is_superuser=True)
    )
    assert response.status_code == 201
    user = get_user_model().objects.get(pk=response.data["id"])
    assert not user.is_staff
    assert not user.is_superuser


def test_coordinator_creates_pending_accounts_only_in_assigned_program(institution):
    client, admin, root, program, offering = institution
    other_program = Scope.objects.create(kind="program", label="Medicine", parent=root)
    other_offering = Scope.objects.create(kind="offering", label="MED 101", parent=other_program)
    coordinator = get_user_model().objects.create_user("coordinator")
    RoleAssignment.objects.create(user=coordinator, role_id="program-coordinator", scope=program)
    client.force_login(coordinator)
    session = client.get("/api/auth/session/")
    assert str(program.pk) in {scope["id"] for scope in session.data["scopes"]}
    assert str(other_program.pk) not in {scope["id"] for scope in session.data["scopes"]}
    body = account_body(offering, username="pending.teacher", role="instructor")
    body.pop("password")
    response = client.post("/api/access/coordinator/accounts/", body)
    assert response.status_code == 201, response.data
    user = get_user_model().objects.get(username="pending.teacher")
    assert not user.is_active and not user.has_usable_password()
    assert RoleAssignment.objects.get(user=user).role_id == "instructor"
    assert AuditEvent.objects.filter(action="role.assigned", subject=user).exists()
    dashboard = client.get("/api/access/coordinator/")
    assert dashboard.status_code == 200, dashboard.data
    assert [program["id"] for program in dashboard.data["programs"]] == [str(program.pk)]
    assert [person["username"] for person in dashboard.data["people"]] == ["pending.teacher"]
    assert client.post("/api/access/coordinator/accounts/", body).status_code == 400
    body.update(username="foreign.student", scope=str(other_offering.pk), role="student")
    assert client.post("/api/access/coordinator/accounts/", body).status_code == 403
    body.update(username="forbidden.admin", scope=str(offering.pk), role="administrator")
    assert client.post("/api/access/coordinator/accounts/", body).status_code == 403
    assert client.get("/api/access/dashboard/", {"scope": str(root.pk)}).status_code == 403
    assert (
        not get_user_model()
        .objects.filter(username__in=["foreign.student", "forbidden.admin"])
        .exists()
    )
    client.force_login(admin)
    pending_login = client.post(
        "/api/auth/login/",
        {"username": user.username, "password": TEST_PASSWORD},
    )
    assert pending_login.status_code == 400
    invalid_password = client.post(
        f"/api/access/accounts/{user.pk}/activate/", {"password": "password"}
    )
    assert invalid_password.status_code == 400
    user.refresh_from_db()
    assert not user.is_active and not user.has_usable_password()
    activated = client.post(
        f"/api/access/accounts/{user.pk}/activate/",
        {"password": TEST_PASSWORD},
    )
    assert activated.status_code == 200, activated.data
    user.refresh_from_db()
    assert user.is_active and user.check_password(TEST_PASSWORD)
    assert AuditEvent.objects.filter(action="account.activated", subject=user).exists()
    activated_login = client.post(
        "/api/auth/login/",
        {"username": user.username, "password": TEST_PASSWORD},
    )
    assert activated_login.status_code == 200
