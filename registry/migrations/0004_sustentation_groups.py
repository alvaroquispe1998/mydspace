from django.conf import settings
from django.db import migrations, models


def forwards(apps, schema_editor):
    Group = apps.get_model("registry", "SustentationGroup")
    Record = apps.get_model("registry", "ThesisRecord")

    # Create 1 group per record created date and assign all existing records.
    # Important: avoid __date extraction (timezone quirks on SQLite). Assign per row.
    for rec in Record.objects.filter(group__isnull=True).only("id", "created_at"):
        dt = getattr(rec, "created_at", None)
        if not dt:
            continue
        d = dt.date()
        g, _created = Group.objects.get_or_create(
            date=d,
            defaults={"name": f"SUSTENTACIÓN {d.strftime('%d.%m.%Y')}", "status": "ARMADO"},
        )
        Record.objects.filter(pk=rec.pk, group__isnull=True).update(group_id=g.id)


def backwards(apps, schema_editor):
    Record = apps.get_model("registry", "ThesisRecord")
    Record.objects.update(group=None)
    Group = apps.get_model("registry", "SustentationGroup")
    Group.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0003_dspace_url_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SustentationGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("name", models.CharField(max_length=120)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ARMADO", "Armado"),
                            ("EN_AUDITORIA", "En auditoría"),
                            ("OBSERVADO", "Observado"),
                            ("APROBADO", "Aprobado"),
                            ("POR_PUBLICAR", "Por publicar"),
                            ("PUBLICADO", "Publicado"),
                        ],
                        default="ARMADO",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.PROTECT,
                        related_name="created_sustentation_groups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-date", "-id"]},
        ),
        migrations.AddField(
            model_name="thesisrecord",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="records",
                to="registry.sustentationgroup",
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="thesisrecord",
            name="group",
            field=models.ForeignKey(
                on_delete=models.deletion.PROTECT,
                related_name="records",
                to="registry.sustentationgroup",
            ),
        ),
    ]

