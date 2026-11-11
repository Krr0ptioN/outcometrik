from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
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
    capabilities = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(queryset=Capability.objects.all()),
        required=False,
        allow_empty=False,
    )

    def validate(self, attrs):
        choices = sum(key in attrs for key in ("role", "capability", "capabilities"))
        if choices != 1:
            raise serializers.ValidationError(
                "Supply exactly one role, capability, or capabilities list."
            )
        capabilities = attrs.get("capabilities")
        if capabilities and len({item.pk for item in capabilities}) != len(capabilities):
            raise serializers.ValidationError({"capabilities": "Options must be unique."})
        return attrs


class AssignmentsView(APIView):
    @transaction.atomic
    def post(self, request):
        serializer = AssignmentInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        capabilities = data.pop("capabilities", None)
        try:
            if capabilities is not None:
                assignments = [
                    assign(actor=request.user, capability=capability, **data)
                    for capability in capabilities
                ]
                return Response(
                    {"ids": [str(assignment.pk) for assignment in assignments]}, status=201
                )
            assignment = assign(actor=request.user, **data)
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
