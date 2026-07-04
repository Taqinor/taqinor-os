# Generated for XFLT16 — Cession / sortie de parc. Ajoute des champs additifs
# sur ``Vehicule`` (date_cession, prix_cession, acheteur). Additif,
# multi-société.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0040_parametreremplacementflotte"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicule",
            name="date_cession",
            field=models.DateField(
                blank=True, null=True, verbose_name="Date de cession"
            ),
        ),
        migrations.AddField(
            model_name="vehicule",
            name="prix_cession",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name="Prix de cession (MAD)",
            ),
        ),
        migrations.AddField(
            model_name="vehicule",
            name="acheteur",
            field=models.CharField(
                blank=True, max_length=150, verbose_name="Acheteur"
            ),
        ),
    ]
