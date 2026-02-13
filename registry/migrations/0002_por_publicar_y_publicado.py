from django.db import migrations


def forwards(apps, schema_editor):
    ThesisRecord = apps.get_model("registry", "ThesisRecord")
    ThesisRecord.objects.filter(status="INCLUIDO_EN_LOTE").update(status="POR_PUBLICAR")


def backwards(apps, schema_editor):
    ThesisRecord = apps.get_model("registry", "ThesisRecord")
    ThesisRecord.objects.filter(status="POR_PUBLICAR").update(status="INCLUIDO_EN_LOTE")


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

