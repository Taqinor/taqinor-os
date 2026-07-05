# XCTR16 - Facturation a l'usage depuis le monitoring (kWh supervises / m3
# pompes). Additif : tarif_usage/franchise_incluse/unite_usage tous NULL par
# defaut -> aucun contrat existant ne change de comportement.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sav", "0045_zsav9_ticket_followers"),
    ]

    operations = [
        migrations.AddField(
            model_name="contratmaintenance",
            name="tarif_usage",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text="Vide = pas de facturation à l'usage (comportement actuel).",
                max_digits=10,
                null=True,
                verbose_name="Tarif à l'usage (MAD/unité)",
            ),
        ),
        migrations.AddField(
            model_name="contratmaintenance",
            name="franchise_incluse",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Quantité incluse par période avant facturation (0 si vide).",
                max_digits=12,
                null=True,
                verbose_name="Franchise incluse (unités/période)",
            ),
        ),
        migrations.AddField(
            model_name="contratmaintenance",
            name="unite_usage",
            field=models.CharField(
                blank=True,
                choices=[("kwh", "kWh"), ("m3", "m³")],
                help_text="kWh (monitoring PV) ou m³ (pompage). Vide = pas d'usage.",
                max_length=5,
                null=True,
                verbose_name="Unité d'usage",
            ),
        ),
    ]
