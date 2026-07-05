# Generated manually — XPAI18 régimes d'exonération IR (stagiaire / ANAPEC /
# TAHFIZ) : champs additifs sur ProfilPaie (régime + fenêtre + plafond) et
# BulletinPaie (montant exonéré, tracé pour le 9421).

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI18 — Régimes stagiaire / ANAPEC / TAHFIZ (additif)."""

    dependencies = [
        ("paie", "0030_xpai17_ventilation_analytique"),
    ]

    operations = [
        migrations.AddField(
            model_name="profilpaie",
            name="regime_exoneration",
            field=models.CharField(
                choices=[
                    ("aucun", "Aucun"),
                    ("stagiaire", "Stagiaire"),
                    ("anapec", "ANAPEC"),
                    ("tahfiz", "TAHFIZ"),
                ],
                default="aucun", max_length=10,
                verbose_name="Régime d'exonération IR"),
        ),
        migrations.AddField(
            model_name="profilpaie",
            name="regime_date_debut",
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Régime — date de début"),
        ),
        migrations.AddField(
            model_name="profilpaie",
            name="regime_date_fin",
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Régime — date de fin (fenêtre)"),
        ),
        migrations.AddField(
            model_name="profilpaie",
            name="regime_plafond_mensuel",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("6000"), max_digits=14,
                verbose_name="Régime — plafond mensuel exonéré"),
        ),
        migrations.AddField(
            model_name="bulletinpaie",
            name="montant_exonere_regime",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=14,
                verbose_name="Montant exonéré (régime stagiaire/ANAPEC/TAHFIZ)"),
        ),
    ]
