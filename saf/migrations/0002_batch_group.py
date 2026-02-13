from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("saf", "0001_initial"),
        ("registry", "0004_sustentation_groups"),
    ]

    operations = [
        migrations.AddField(
            model_name="safbatch",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="batches",
                to="registry.sustentationgroup",
            ),
        ),
    ]

