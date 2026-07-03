# Generated manually — XPAI1 solde de tout compte (STC).
#
# Additif : ajoute le type de bulletin STC (nature du bulletin de sortie) et
# le plafond d'exonération IR de l'indemnité de licenciement sur
# ParametrePaie. Défauts inchangés pour les données existantes.

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI1 — Solde de tout compte (STC)."""

    dependencies = [
        ("paie", "0021_ordrevirement_reference_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="parametrepaie",
            name="plafond_exoneration_ir_indemnite_licenciement",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("1000000"), max_digits=14,
                verbose_name="Plafond exonération IR indemnité de licenciement"),
        ),
        migrations.AlterField(
            model_name="bulletinpaie",
            name="type_bulletin",
            field=models.CharField(
                choices=[("normal", "Normal"),
                         ("rectificatif", "Rectificatif"),
                         ("rappel", "Rappel"),
                         ("stc", "Solde de tout compte")],
                default="normal", max_length=14,
                verbose_name="Nature du bulletin"),
        ),
    ]
