# Generated for FG155 — contract start/end dates on DossierEmploye.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dossieremploye",
            name="contrat_date_debut",
            field=models.DateField(
                blank=True, null=True, verbose_name="Début de contrat"
            ),
        ),
        migrations.AddField(
            model_name="dossieremploye",
            name="contrat_date_fin",
            field=models.DateField(
                blank=True, null=True, verbose_name="Fin de contrat"
            ),
        ),
    ]
