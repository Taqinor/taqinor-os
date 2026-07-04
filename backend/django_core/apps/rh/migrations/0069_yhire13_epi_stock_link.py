# Generated manually — YHIRE13 lien EpiCatalogue -> stock.Produit (référence
# string, jamais de FK cross-app) + suivi de restitution DotationEpi.
# Additif, aucune donnée existante touchée.

from django.db import migrations, models


class Migration(migrations.Migration):
    """YHIRE13 — EpiCatalogue.produit_id + DotationEpi.restituee/date_restitution
    (additif)."""

    dependencies = [
        ("rh", "0068_yhire5_avance_paie_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="epicatalogue",
            name="produit_id",
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Produit stock lié (référence)"),
        ),
        migrations.AddField(
            model_name="dotationepi",
            name="restituee",
            field=models.BooleanField(default=False, verbose_name="Restituée"),
        ),
        migrations.AddField(
            model_name="dotationepi",
            name="date_restitution",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Date de restitution"),
        ),
    ]
