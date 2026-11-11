"""Disposable local API for browser tests; never points at a real institution DB."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))


def main():
    with tempfile.TemporaryDirectory(prefix="outcometrik-auth-e2e-") as directory:
        os.environ.update(
            {
                "DJANGO_SETTINGS_MODULE": "config.settings",
                "DJANGO_DEBUG": "true",
                "DJANGO_SECRET_KEY": "browser-tests-only-not-a-production-secret",
                "DJANGO_DB_ENGINE": "django.db.backends.sqlite3",
                "DJANGO_SQLITE_NAME": str(Path(directory) / "test.sqlite3"),
                "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "http://127.0.0.1:3000,http://localhost:3000",
            }
        )
        import django

        django.setup()
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        call_command("migrate", verbosity=0)
        get_user_model().objects.create_user(
            "institution.admin",
            password="E2e-Admin-Password-2026!",
            email="admin@example.edu",
            first_name="Alex",
            last_name="Morgan",
        )
        call_command(
            "bootstrap_access", "institution.admin", name="Northbridge University"
        )
        call_command("runserver", "127.0.0.1:8000", use_reloader=False)


if __name__ == "__main__":
    main()
