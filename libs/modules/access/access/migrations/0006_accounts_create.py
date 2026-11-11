# ruff: noqa: RUF012
from django.db import migrations


def grant(apps, schema_editor):
    alias = schema_editor.connection.alias
    capability, _ = (
        apps.get_model("access", "Capability")
        .objects.using(alias)
        .get_or_create(code="accounts.create")
    )
    role = apps.get_model("access", "Role").objects.using(alias).get(slug="program-coordinator")
    role.capabilities.add(capability)


class Migration(migrations.Migration):
    dependencies = [("access", "0005_institutionmembership")]
    operations = [migrations.RunPython(grant, migrations.RunPython.noop)]
