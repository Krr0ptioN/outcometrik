from ..models import Assessment
from .base import AcademicService
from .grades import _editable_offering_ids


class AssessmentService(AcademicService):
    """Expose approved assessment choices only to staff who can edit their offering."""

    model = Assessment

    def visible_queryset(self, queryset):
        candidates = (
            Assessment.objects.filter(status=Assessment.Status.APPROVED)
            .values_list("offering_id", flat=True)
            .distinct()
        )
        return queryset.filter(
            status=Assessment.Status.APPROVED,
            offering_id__in=_editable_offering_ids(self.actor, candidates),
        )
