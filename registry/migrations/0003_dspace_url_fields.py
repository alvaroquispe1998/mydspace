from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0002_por_publicar_y_publicado"),
    ]

    operations = [
        migrations.AddField(
            model_name="thesisrecord",
            name="dspace_handle",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="thesisrecord",
            name="dspace_url",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]

