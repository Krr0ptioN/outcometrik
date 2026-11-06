from .models import Enrollment


def eligible_roster(offering):
    """Enrollments that count toward outcomes, with status and attempt data."""
    return (
        Enrollment.objects.filter(offering=offering, eligible_for_outcomes=True)
        .select_related("student")
        .order_by("student_id")
    )


def input_revision(offering) -> tuple[int, int]:
    """(program revision, offering revision) for stale-result detection."""
    offering.refresh_from_db(fields=["input_revision"])
    offering.program.refresh_from_db(fields=["input_revision"])
    return offering.program.input_revision, offering.input_revision
