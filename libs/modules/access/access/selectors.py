from django.db.models import Q
from django.shortcuts import get_object_or_404

from .policy import authorization


def visible_resources(queryset, *, principal, capability):
    """Contract: scope FK, owner_id, released and published are domain-owned fields."""
    if not principal or not principal.is_authenticated or not principal.is_active:
        return queryset.none()
    visible = authorization.scope_filter(principal, capability)
    if capability in {"grades.view", "evidence.view", "outcomes.view"}:
        publication = Q(published=True) if capability == "outcomes.view" else Q(released=True)
        visible |= (
            authorization.student_filter(principal, capability)
            & Q(owner_id=principal.pk)
            & publication
        )
    return queryset.filter(visible).distinct()


def visible_resource(queryset, *, principal, capability, pk):
    return get_object_or_404(
        visible_resources(queryset, principal=principal, capability=capability),
        pk=pk,
    )
