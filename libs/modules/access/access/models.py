# ruff: noqa: RUF012
"""Authorization state; mutations belong to access.services."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Scope(models.Model):
    class Kind(models.TextChoices):
        INSTITUTION = "institution"
        PROGRAM = "program"
        OFFERING = "offering"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    label = models.CharField(max_length=160, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)

    def clean(self):
        expected = {self.Kind.PROGRAM: self.Kind.INSTITUTION, self.Kind.OFFERING: self.Kind.PROGRAM}
        if self.kind == self.Kind.INSTITUTION:
            valid = self.parent_id is None
        else:
            valid = self.parent_id is not None and self.parent.kind == expected.get(self.kind)
        if not valid:
            raise ValidationError("Invalid scope hierarchy.")
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            old = type(self).objects.get(pk=self.pk)
            if (old.kind, old.parent_id) != (self.kind, self.parent_id):
                raise ValidationError("Scope ancestry is immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class InstitutionMembership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    institution = models.ForeignKey(Scope, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "institution"], name="unique_institution_member"
            )
        ]


class Capability(models.Model):
    code = models.CharField(max_length=100, primary_key=True)


class Role(models.Model):
    slug = models.SlugField(primary_key=True)
    name = models.CharField(max_length=100)
    scope_kind = models.CharField(max_length=16, choices=Scope.Kind.choices)
    capabilities = models.ManyToManyField(Capability)


class Assignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    scope = models.ForeignKey(Scope, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["user", "scope", "revoked_at"])]


class RoleAssignment(Assignment):
    role = models.ForeignKey(Role, on_delete=models.PROTECT)

    class Meta(Assignment.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["user", "scope", "role"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_role",
            )
        ]


class DirectCapabilityGrant(Assignment):
    capability = models.ForeignKey(Capability, on_delete=models.PROTECT)

    class Meta(Assignment.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["user", "scope", "capability"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_grant",
            )
        ]


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit events are immutable.")

    def delete(self):
        raise ValidationError("Audit events are immutable.")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("Audit events are immutable.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+"
    )
    scope = models.ForeignKey(Scope, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict)
    objects = AppendOnlyQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are immutable.")
