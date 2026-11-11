"""Same-origin session authentication, including CSRF validation before login."""

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .models import Scope
from .policy import authorization


def user_data(user):
    return {
        key: getattr(user, key)
        for key in ("id", "username", "email", "first_name", "last_name", "is_active")
    }


def scope_data(scope):
    return {
        "id": str(scope.pk),
        "kind": scope.kind,
        "label": scope.label or f"{scope.get_kind_display()} {str(scope.pk)[:8]}",
        "parent_id": str(scope.parent_id) if scope.parent_id else None,
    }


def manageable_scopes(user):
    return Scope.objects.filter(
        authorization.scope_filter(user, "access.manage", prefix="")
    ).order_by("kind", "label", "id")


def session_data(user):
    if not user.is_authenticated:
        return {"user": None, "scopes": []}
    authorized = Scope.objects.filter(
        authorization.scope_filter(user, "accounts.create", prefix="")
    )
    scopes = (manageable_scopes(user) | authorized).distinct().order_by("kind", "label", "id")
    return {"user": user_data(user), "scopes": [scope_data(s) for s in scopes]}


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        get_token(request)
        response = Response(session_data(request.user))
        response["Cache-Control"] = "no-store"
        return response


class LoginInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=1024, trim_whitespace=False, write_only=True)


class LoginThrottle(SimpleRateThrottle):
    rate = "10/min"
    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (LoginThrottle,)

    def post(self, request):
        serializer = LoginInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request=request, **serializer.validated_data)
        if user is None:
            return Response({"detail": "Invalid username or password."}, status=400)
        login(request, user)
        response = Response(session_data(user))
        response["Cache-Control"] = "no-store"
        return response


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    def post(self, request):
        logout(request)
        response = Response({"user": None, "scopes": []})
        response["Cache-Control"] = "no-store"
        return response
