from django.db.models import F

from ..models import CourseOffering, Program


class RevisionTracker:
    """Update outcome input revisions within the caller's transaction."""

    @staticmethod
    def bump(*, program_id, offering_id=None):
        Program.objects.filter(pk=program_id).update(input_revision=F("input_revision") + 1)
        if offering_id is not None:
            CourseOffering.objects.filter(pk=offering_id).update(
                input_revision=F("input_revision") + 1
            )
