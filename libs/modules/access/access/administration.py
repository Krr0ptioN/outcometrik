"""Scope-filtered administration APIs. Account creation always includes a role."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .identity import manageable_scopes, scope_data, user_data
from .models import (
    AuditEvent,
    Capability,
    DirectCapabilityGrant,
    InstitutionMembership,
    Role,
    RoleAssignment,
    Scope,
)
from .policy import authorization
from .services import assign


def selected_scopes(actor, scope):
    authorization.require(principal=actor, capability="access.manage", scope=scope)
    return manageable_scopes(actor).filter(
        Q(pk=scope.pk) | Q(parent_id=scope.pk) | Q(parent__parent_id=scope.pk)
    )


class DashboardInput(serializers.Serializer):
    scope = serializers.PrimaryKeyRelatedField(queryset=Scope.objects.all())

    def validate_scope(self, value):
        if value.kind != Scope.Kind.INSTITUTION:
            raise serializers.ValidationError("Select an institution scope.")
        return value

    search = serializers.CharField(required=False, default="", allow_blank=True, max_length=150)
    page = serializers.IntegerField(required=False, default=1, min_value=1)


class DashboardView(APIView):
    def get(self, request):
        serializer = DashboardInput(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        scopes = selected_scopes(request.user, data["scope"])
        roles = RoleAssignment.objects.filter(scope__in=scopes, revoked_at__isnull=True)
        grants = DirectCapabilityGrant.objects.filter(scope__in=scopes, revoked_at__isnull=True)
        users = get_user_model().objects.filter(
            Q(pk__in=roles.values("user_id"))
            | Q(pk__in=grants.values("user_id"))
            | Q(
                pk__in=InstitutionMembership.objects.filter(institution=data["scope"]).values(
                    "user_id"
                )
            )
        )
        counts = {
            "users": users.count(),
            "roles": roles.count(),
            "grants": grants.count(),
            "scopes": scopes.count(),
            "programs": scopes.filter(kind="program").count(),
            "offerings": scopes.filter(kind="offering").count(),
        }
        search = data["search"]
        if search:
            users = users.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        total = users.count()
        page_users = list(
            users.order_by("username", "pk")[(data["page"] - 1) * 20 : data["page"] * 20]
        )
        ids = [u.pk for u in page_users]
        role_rows = list(
            roles.filter(user_id__in=ids).values("id", "user_id", "scope_id", "role_id")
        )
        grant_rows = list(
            grants.filter(user_id__in=ids).values("id", "user_id", "scope_id", "capability_id")
        )
        people = [
            {
                **user_data(user),
                "roles": [r for r in role_rows if r["user_id"] == user.pk],
                "grants": [g for g in grant_rows if g["user_id"] == user.pk],
            }
            for user in page_users
        ]
        audit = (
            AuditEvent.objects.filter(scope__in=scopes)
            .select_related("actor", "subject")
            .order_by("-occurred_at", "-id")[:20]
        )
        response = Response(
            {
                "scope_id": str(data["scope"].pk),
                "scopes": [scope_data(s) for s in scopes],
                "roles": list(Role.objects.order_by("name").values("slug", "name", "scope_kind")),
                "capabilities": list(
                    Capability.objects.order_by("code").values_list("code", flat=True)
                ),
                "users": people,
                "counts": counts,
                "total": total,
                "page": data["page"],
                "page_size": 20,
                "audit": [
                    {
                        "id": str(event.pk),
                        "action": event.action,
                        "actor": event.actor.username,
                        "subject": event.subject.username if event.subject else None,
                        "scope_id": str(event.scope_id),
                        "occurred_at": event.occurred_at,
                    }
                    for event in audit
                ],
            }
        )
        response["Cache-Control"] = "no-store"
        return response


class AccountInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, default="", allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, default="", allow_blank=True)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)
    scope = serializers.PrimaryKeyRelatedField(queryset=Scope.objects.all())
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())

    def validate_username(self, value):
        field = get_user_model()._meta.get_field("username")
        try:
            field.run_validators(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value


@transaction.atomic
def create_account(*, actor, scope, role, password, **fields):
    authorization.require(principal=actor, capability="access.manage", scope=scope)
    user = get_user_model()(**fields)
    user.full_clean(exclude=["password", "last_login", "date_joined"])
    validate_password(password, user)
    user.set_password(password)
    user.save()
    assign(actor=actor, user=user, scope=scope, role=role)
    AuditEvent.objects.create(
        actor=actor,
        subject=user,
        scope=scope,
        action="account.created",
        metadata={"username": user.username},
    )
    return user


class AccountsView(APIView):
    def post(self, request):
        serializer = AccountInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = create_account(actor=request.user, **serializer.validated_data)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        except IntegrityError as exc:
            raise serializers.ValidationError("This username is already in use.") from exc
        return Response(user_data(user), status=201)


class CoordinatorDashboardView(APIView):
    def get(self, request):
        programs = Scope.objects.filter(
            authorization.scope_filter(request.user, "accounts.create", prefix=""),
            kind="program",
        )
        offerings = Scope.objects.filter(parent__in=programs, kind="offering")
        assignments = RoleAssignment.objects.filter(
            scope__in=offerings, revoked_at__isnull=True, role_id__in=("instructor", "student")
        ).select_related("user", "scope")
        return Response(
            {
                "programs": [scope_data(p) for p in programs],
                "offerings": [scope_data(o) for o in offerings],
                "people": [
                    {**user_data(a.user), "role": a.role_id, "offering_id": str(a.scope_id)}
                    for a in assignments
                ],
            }
        )


class CoordinatorAccountsView(APIView):
    @transaction.atomic
    def post(self, request):
        serializer = CoordinatorAccountInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        scope, role = serializer.validated_data["scope"], serializer.validated_data["role"]
        if (
            scope.kind != Scope.Kind.OFFERING
            or role.pk not in {"instructor", "student"}
            or not authorization.allows(
                principal=request.user, capability="accounts.create", scope=scope
            )
        ):
            raise APIPermissionDenied("This action is not permitted in this scope.")
        fields = {
            k: serializer.validated_data[k]
            for k in ("username", "email", "first_name", "last_name")
        }
        user = get_user_model()(**fields, is_active=False)
        user.set_unusable_password()
        try:
            user.full_clean(exclude=["password", "last_login", "date_joined"])
            user.save()
            RoleAssignment.objects.create(user=user, scope=scope, role=role)
            institution = scope.parent.parent
            InstitutionMembership.objects.get_or_create(user=user, institution=institution)
        except (ValidationError, IntegrityError) as exc:
            raise serializers.ValidationError("Invalid or duplicate account.") from exc
        AuditEvent.objects.create(
            actor=request.user,
            subject=user,
            scope=scope,
            action="account.created",
            metadata={"username": user.username, "pending": True},
        )
        return Response(user_data(user), status=201)


class CoordinatorAccountInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, default="", allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, default="", allow_blank=True)
    scope = serializers.PrimaryKeyRelatedField(queryset=Scope.objects.all())
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())

    def validate_username(self, value):
        try:
            get_user_model()._meta.get_field("username").run_validators(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value


class ActivateAccountView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        user = get_object_or_404(get_user_model(), pk=pk, is_active=False)
        assignment = get_object_or_404(
            RoleAssignment.objects.filter(user=user, revoked_at__isnull=True)
        )
        authorization.require(
            principal=request.user, capability="access.manage", scope=assignment.scope
        )
        password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)
        field = password.run_validation(request.data.get("password"))
        try:
            validate_password(field, user)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        user.set_password(field)
        user.is_active = True
        user.save(update_fields=["password", "is_active"])
        AuditEvent.objects.create(
            actor=request.user,
            subject=user,
            scope=assignment.scope,
            action="account.activated",
            metadata={"username": user.username},
        )
        return Response(user_data(user))


class ScopeInput(serializers.Serializer):
    label = serializers.CharField(max_length=160)
    kind = serializers.ChoiceField(choices=["program", "offering"])
    parent = serializers.PrimaryKeyRelatedField(queryset=Scope.objects.all())


class ScopesView(APIView):
    @transaction.atomic
    def post(self, request):
        serializer = ScopeInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        authorization.require(
            principal=request.user, capability="access.manage", scope=data["parent"]
        )
        scope = Scope(**data)
        try:
            scope.save()
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        AuditEvent.objects.create(
            actor=request.user,
            scope=scope,
            action="scope.created",
            metadata={"label": scope.label, "kind": scope.kind},
        )
        return Response(scope_data(scope), status=201)
