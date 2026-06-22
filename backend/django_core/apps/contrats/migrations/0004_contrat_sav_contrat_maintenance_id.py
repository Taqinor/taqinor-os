from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contrats", "0003_contratlien"),
    ]

    operations = [
        migrations.AddField(
            model_name="contrat",
            name="sav_contrat_maintenance_id",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="ID du contrat de maintenance SAV",
            ),
        ),
    ]
