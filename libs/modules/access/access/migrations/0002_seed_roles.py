# ruff: noqa: RUF012
from django.db import migrations

CAPABILITIES = (
    "access.manage",
    "program.manage",
    "offering.manage",
    "grades.view",
    "grades.edit",
    "grades.release",
    "outcomes.view",
    "evidence.view",
    "faculty.preview",
    "grades.export",
)
ROLES = (
    ("administrator", "Administrator", "institution", CAPABILITIES),
    (
        "program-coordinator",
        "Program Coordinator",
        "program",
        tuple(code for code in CAPABILITIES if code != "access.manage"),
    ),
    (
        "instructor",
        "Instructor",
        "offering",
        (
            "offering.manage",
            "grades.view",
            "grades.edit",
            "outcomes.view",
            "evidence.view",
            "faculty.preview",
        ),
    ),
    ("student", "Student", "offering", ("grades.view", "outcomes.view", "evidence.view")),
)


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    capability_model = apps.get_model("access", "Capability")
    role_model = apps.get_model("access", "Role")
    for code in CAPABILITIES:
        capability_model.objects.using(alias).create(code=code)
    for slug, name, kind, codes in ROLES:
        role = role_model.objects.using(alias).create(slug=slug, name=name, scope_kind=kind)
        role.capabilities.add(*capability_model.objects.using(alias).filter(code__in=codes))


class Migration(migrations.Migration):
    dependencies = [("access", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
