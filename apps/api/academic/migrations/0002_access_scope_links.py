from django.db import migrations


def create_scopes(apps, schema_editor):
    Institution = apps.get_model("academic", "Institution")
    Program = apps.get_model("academic", "Program")
    CourseOffering = apps.get_model("academic", "CourseOffering")
    Scope = apps.get_model("access", "Scope")
    db = schema_editor.connection.alias
    for institution in Institution.objects.using(db).all():
        Scope.objects.using(db).get_or_create(
            pk=institution.pk,
            defaults={"kind": "institution", "label": institution.name, "parent_id": None},
        )
    for program in Program.objects.using(db).select_related("department__institution"):
        Scope.objects.using(db).get_or_create(
            pk=program.pk,
            defaults={
                "kind": "program",
                "label": program.title,
                "parent_id": program.department.institution_id,
            },
        )
    for offering in CourseOffering.objects.using(db).select_related("course"):
        Scope.objects.using(db).get_or_create(
            pk=offering.pk,
            defaults={
                "kind": "offering",
                "label": f"{offering.course.code} {offering.section}",
                "parent_id": offering.program_id,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("academic", "0001_initial"),
        ("access", "0006_accounts_create"),
    ]

    operations = [migrations.RunPython(create_scopes, migrations.RunPython.noop)]
