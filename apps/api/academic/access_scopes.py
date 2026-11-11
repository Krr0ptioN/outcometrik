"""Keep academic records addressable by the matching access-policy scopes."""

from access.models import Scope
from django.core.exceptions import ValidationError


def sync_scope(record):
    if record.pk is None:
        return
    if record.__class__.__name__ == "Institution":
        kind, parent_id, label = Scope.Kind.INSTITUTION, None, record.name
    elif record.__class__.__name__ == "Program":
        kind = Scope.Kind.PROGRAM
        parent_id = record.department.institution_id
        label = record.title
    elif record.__class__.__name__ == "CourseOffering":
        kind = Scope.Kind.OFFERING
        parent_id = record.program_id
        label = f"{record.course.code} {record.section}"
    else:
        return
    scope, created = Scope.objects.get_or_create(
        pk=record.pk,
        defaults={"kind": kind, "parent_id": parent_id, "label": label},
    )
    if not created and (scope.kind != kind or scope.parent_id != parent_id):
        raise ValidationError("Academic record does not match its authorization scope.")
    if scope.label != label:
        scope.label = label
        scope.save(update_fields=["label"])
