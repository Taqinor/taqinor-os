# YSUBS9 — Période de service (du/au) sur les factures récurrentes. Additive,
# NULL par défaut = comportement actuel intact pour toute facture existante
# et pour toute facture non récurrente.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0063_xctr22_mandat_paiement"),
    ]

    operations = [
        migrations.AddField(
            model_name="facture",
            name="periode_service_debut",
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Période de service — début"),
        ),
        migrations.AddField(
            model_name="facture",
            name="periode_service_fin",
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Période de service — fin"),
        ),
    ]
