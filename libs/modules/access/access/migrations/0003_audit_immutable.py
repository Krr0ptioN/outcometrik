# ruff: noqa: RUF012
"""Database enforcement also protects bulk operations and raw SQL."""

from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION access_reject_audit_mutation() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'Audit events are immutable'; END;
            $$ LANGUAGE plpgsql;
        """)
        schema_editor.execute("""
            CREATE TRIGGER access_audit_immutable BEFORE UPDATE OR DELETE
            ON access_auditevent FOR EACH ROW EXECUTE FUNCTION access_reject_audit_mutation();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        for action in ("UPDATE", "DELETE"):
            schema_editor.execute(f"""
                CREATE TRIGGER access_audit_no_{action.lower()} BEFORE {action}
                ON access_auditevent BEGIN SELECT RAISE(ABORT, 'Audit events are immutable'); END;
            """)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER access_audit_immutable ON access_auditevent")
        schema_editor.execute("DROP FUNCTION access_reject_audit_mutation()")
    elif schema_editor.connection.vendor == "sqlite":
        for action in ("update", "delete"):
            schema_editor.execute(f"DROP TRIGGER access_audit_no_{action}")


class Migration(migrations.Migration):
    dependencies = [("access", "0002_seed_roles")]
    operations = [migrations.RunPython(install, uninstall)]
