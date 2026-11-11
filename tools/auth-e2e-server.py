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
        from academic.models import (
            AcademicTerm,
            Course,
            Department,
            Institution,
            Program,
            ProgramCourse,
        )
        from academic.services import CourseOfferingService
        from access.models import Scope

        admin = get_user_model().objects.get(username="institution.admin")
        institution_scope = Scope.objects.get(
            kind=Scope.Kind.INSTITUTION, label="Northbridge University"
        )
        institution = Institution.objects.create(
            pk=institution_scope.pk, code="NORTHBRIDGE", name="Northbridge University"
        )
        department = Department.objects.create(
            institution=institution, code="CSE", name="Computer Science"
        )
        program = Program.objects.create(
            department=department, code="CSE", title="Computer Engineering"
        )
        term = AcademicTerm.objects.create(
            institution=institution,
            year=2026,
            season="fall",
            starts_at="2026-09-01",
            ends_at="2027-01-15",
        )
        course = Course.objects.create(
            home_department=department,
            code="CSE301",
            title="Algorithms",
            ects=6,
            credits=3,
        )
        ProgramCourse.objects.create(
            program=program,
            course=course,
            effective_from="2026-01-01",
            status="approved",
        )
        CourseOfferingService(actor=admin).create(
            program=program, course=course, term=term, section="01"
        )
        call_command("runserver", "127.0.0.1:8000", use_reloader=False)


if __name__ == "__main__":
    main()
