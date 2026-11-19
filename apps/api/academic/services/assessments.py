from typing import Any

from access.policy import AuthorizationService
from wireup import injectable

from ..access_control import OfferingAuthorization
from ..models import Assessment


@injectable
class AssessmentService:
    """Expose approved assessment choices only to staff who can edit their offering."""

    model = Assessment

    def __init__(self, auth_service: AuthorizationService | None = None, *, actor: Any = None):
        self.auth_service = auth_service or AuthorizationService()
        self.actor = actor

    def get_queryset(self, actor: Any = None, **filters):
        effective_actor = actor if actor is not None else self.actor
        qs = self.visible_queryset(Assessment.objects.all(), actor=effective_actor)
        if filters:
            valid_fields = {f.name for f in self.model._meta.get_fields()}
            clean = {k: v for k, v in filters.items() if k in valid_fields}
            if clean:
                qs = qs.filter(**clean)
        return qs.order_by("created_at", "id")

    def visible_queryset(self, queryset=None, actor: Any = None):
        if queryset is None:
            queryset = Assessment.objects.all()
        effective_actor = actor if actor is not None else self.actor
        candidates = (
            Assessment.objects.filter(status=Assessment.Status.APPROVED)
            .values_list("offering_id", flat=True)
            .distinct()
        )
        return queryset.filter(
            status=Assessment.Status.APPROVED,
            offering_id__in=OfferingAuthorization.editable_ids(
                actor=effective_actor, candidate_ids=candidates
            ),
        )
