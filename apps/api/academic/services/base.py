from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from ..access_control import require


class AcademicService:
    """Request-scoped base for scoped academic queries and writes."""

    model = None
    immutable_fields = ()

    def __init__(self, *, actor):
        self.actor = actor

    def visible_queryset(self, queryset):
        return queryset

    def get_queryset(self):
        return self.visible_queryset(self.model.objects.all())

    def create_access(self, data):
        return "access.manage", None

    def update_access(self, instance):
        return "access.manage", None

    def validate_create(self, data):
        return None

    def validate_update(self, instance, data):
        for field in self.immutable_fields:
            if field in data and data[field] != getattr(instance, field):
                raise ValidationError({field: "This field cannot be changed."})

    @staticmethod
    def check_access(actor, capability, scope_id):
        if scope_id is None:
            raise PermissionDenied("This action is not permitted in this scope.")
        require(actor, capability, scope_id)

    @transaction.atomic
    def create(self, **data):
        capability, scope_id = self.create_access(data)
        self.check_access(self.actor, capability, scope_id)
        self.validate_create(data)
        try:
            return self.model.objects.create(**data)
        except IntegrityError as exc:
            raise ValidationError(
                "This academic record conflicts with an existing record."
            ) from exc

    @transaction.atomic
    def update(self, *, instance, **data):
        capability, scope_id = self.update_access(instance)
        self.check_access(self.actor, capability, scope_id)
        self.validate_update(instance, data)
        for field, value in data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            raise ValidationError(
                "This academic record conflicts with an existing record."
            ) from exc
        return instance
