# ruff: noqa: RUF012
from django.db import migrations

GRANTS = (("outcomes.publish", ("administrator", "program-coordinator")),)


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
        capability = capability_model.objects.using(alias).filter(code=code).first()
        if capability is None:
            continue
        for role in role_model.objects.using(alias).filter(slug__in=roles):
            role.capabilities.remove(capability)


class Migration(migrations.Migration):
    dependencies = [("access", "0007_syllabus_capabilities")]
    operations = [migrations.RunPython(grant, revoke)]
