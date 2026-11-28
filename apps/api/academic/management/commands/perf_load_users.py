"""Give the PERF-01 benchmark users a known password for load tests.

The seed creates users with unusable passwords. k6 needs to log in, so this sets one
password (from PERF_LOAD_PASSWORD, never hardcoded) on the coordinator and the first N
students of an already-seeded benchmark database. No rows are created or deleted.
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from academic.models import Institution

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "")


class Command(BaseCommand):
    help = "Set PERF_LOAD_PASSWORD on the benchmark coordinator and first N students."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=5)
        parser.add_argument("--allow-remote", action="store_true")

    def handle(self, *args, **opts):
        db = settings.DATABASES["default"]
        if db["NAME"] == "outcometrik":
            raise CommandError("Refusing to touch the dev database 'outcometrik'.")
        if db.get("HOST", "") not in LOCAL_HOSTS and not opts["allow_remote"]:
            raise CommandError("Refusing a non-local database without --allow-remote.")
        password = os.environ.get("PERF_LOAD_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("Set PERF_LOAD_PASSWORD (at least 12 characters).")
        if not Institution.objects.filter(code="PERF").exists():
            raise CommandError("Institution PERF not found: seed the benchmark DB first.")

        names = ["perf.coordinator"] + [
            f"perf.student.{i:05d}" for i in range(1, opts["students"] + 1)
        ]
        updated = (
            get_user_model()
            .objects.filter(username__in=names)
            .update(password=make_password(password))
        )
        if updated != len(names):
            raise CommandError(f"Expected {len(names)} users, updated {updated}.")
        self.stdout.write(self.style.SUCCESS(f"Password set for {updated} benchmark users."))
