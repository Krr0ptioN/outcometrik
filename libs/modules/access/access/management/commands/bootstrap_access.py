from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from access.models import AuditEvent, InstitutionMembership, Role, RoleAssignment, Scope


class Command(BaseCommand):
    help = "Bootstrap the first institution administrator (trusted operator only)."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--name", default="My institution")

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"], is_active=True).first()
        if user is None:
            raise CommandError("An existing active user is required.")
        if Scope.objects.exists():
            raise CommandError("Access is already initialized; use the assignment service.")
        scope = Scope.objects.create(kind=Scope.Kind.INSTITUTION, label=options["name"])
        InstitutionMembership.objects.create(user=user, institution=scope)
        assignment = RoleAssignment.objects.create(
            user=user, scope=scope, role=Role.objects.get(pk="administrator")
        )
        AuditEvent.objects.create(
            actor=user,
            subject=user,
            scope=scope,
            action="role.assigned",
            metadata={"assignment_id": str(assignment.pk), "bootstrap": True},
        )
        self.stdout.write(str(scope.pk))
