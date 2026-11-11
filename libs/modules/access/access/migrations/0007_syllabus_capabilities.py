# ruff: noqa: RUF012
from django.db import migrations

GRANTS = (
    ("syllabus.draft", ("administrator", "program-coordinator", "instructor")),
    ("syllabus.approve", ("administrator", "program-coordinator")),
)


def grant(apps, schema_editor):
    alias = schema_editor.connection.alias
    capability_model = apps.get_model("access", "Capability")
    role_model = apps.get_model("access", "Role")
    for code, roles in GRANTS:
        capability, _ = capability_model.objects.using(alias).get_or_create(code=code)
        for slug in roles:
            role_model.objects.using(alias).get(slug=slug).capabilities.add(capability)


def revoke(apps, schema_editor):
    alias = schema_editor.connection.alias
    capability_model = apps.get_model("access", "Capability")
    role_model = apps.get_model("access", "Role")
    for code, roles in GRANTS:
        role_model.objects.using(alias).filter(slug__in=roles).remove(
            *capability_model.objects.using(alias).filter(code=code)
        )


class Migration(migrations.Migration):
    dependencies = [("access", "0006_accounts_create")]
    operations = [migrations.RunPython(grant, revoke)]
