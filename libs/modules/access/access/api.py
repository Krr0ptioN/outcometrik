from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Capability, DirectCapabilityGrant, Role, RoleAssignment, Scope
from .policy import authorization
from .services import assign, revoke


class AssignmentInput(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all())
    scope = serializers.PrimaryKeyRelatedField(queryset=Scope.objects.all())
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), required=False)
    capability = serializers.PrimaryKeyRelatedField(
        queryset=Capability.objects.all(), required=False
    )

    def validate(self, attrs):
        if ("role" in attrs) == ("capability" in attrs):
            raise serializers.ValidationError("Supply exactly one role or capability.")
        return attrs


class AssignmentsView(APIView):
    def post(self, request):
        serializer = AssignmentInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = assign(actor=request.user, **serializer.validated_data)
        except PermissionDenied as exc:
            raise APIPermissionDenied(str(exc)) from exc
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return Response({"id": str(assignment.pk)}, status=201)


class RevokeView(APIView):
    def delete(self, request, kind, pk):
        model = {"roles": RoleAssignment, "grants": DirectCapabilityGrant}[kind]
        # Hide assignments outside scopes the actor can administer.
        queryset = model.objects.filter(authorization.scope_filter(request.user, "access.manage"))
        assignment = get_object_or_404(queryset, pk=pk)
        try:
            revoke(actor=request.user, assignment=assignment)
        except PermissionDenied as exc:
            raise APIPermissionDenied(str(exc)) from exc
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return Response(status=204)
