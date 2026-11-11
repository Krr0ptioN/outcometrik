"""Translate academic records to the scope and capability required for an action."""

from access.models import Scope
from access.policy import authorization
from django.core.exceptions import PermissionDenied


def require(actor, capability, scope_id):
    try:
        scope = Scope.objects.get(pk=scope_id)
    except Scope.DoesNotExist as exc:
        raise PermissionDenied("This action is not permitted in this scope.") from exc
    authorization.require(principal=actor, capability=capability, scope=scope)


def require_institution(actor, capability, institution_id):
    require(actor, capability, institution_id)


def require_program(actor, capability, program_id):
    require(actor, capability, program_id)


def require_offering(actor, capability, offering_id):
    require(actor, capability, offering_id)
