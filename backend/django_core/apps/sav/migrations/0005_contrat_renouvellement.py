# N47 — durée + date de renouvellement sur le contrat de maintenance. Additif,
# nullable : NULL = comportement actuel (contrat sans échéance fixée).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sav", "0004_piececonsommee"),
    ]

    operations = [
        migrations.AddField(
            model_name="contratmaintenance",
            name="duree_mois",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contratmaintenance",
            name="date_renouvellement",
            field=models.DateField(blank=True, null=True),
        ),
    ]
