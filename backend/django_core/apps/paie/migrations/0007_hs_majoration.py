# Generated manually — PAIE14 heures supplémentaires majorées.
#
# Additive et réversible :
# * ``ParametrePaie`` : trois nouveaux champs décimaux (taux_hs_jour/nuit/ferie)
#   avec leurs valeurs réglementaires marocaines par défaut (25/50/100 %).
# * ``ElementVariable`` : un nouveau champ CharField ``categorie_hs`` (choix
#   jour/nuit/ferie, défaut 'jour', blank autorisé) pour qualifier la nature
#   des heures supplémentaires.

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE14 — Heures supplémentaires majorées (25/50/100 % jour/nuit/férié).

    Ajoute les taux de majoration HS éditables au ``ParametrePaie`` et la
    catégorie HS (jour/nuit/ferie) à ``ElementVariable``. Migration purement
    additive, réversible.
    """

    dependencies = [
        ("paie", "0006_profilpaie_jours_travail_mensuel_heures_travail_mensuel"),
    ]

    operations = [
        # ── ParametrePaie : taux de majoration HS ──────────────────────────
        migrations.AddField(
            model_name="parametrepaie",
            name="taux_hs_jour",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("25"),
                max_digits=6,
                verbose_name="Majoration HS jour (%)",
            ),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="taux_hs_nuit",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("50"),
                max_digits=6,
                verbose_name="Majoration HS nuit (%)",
            ),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="taux_hs_ferie",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("100"),
                max_digits=6,
                verbose_name="Majoration HS férié/dimanche (%)",
            ),
        ),
        # ── ElementVariable : catégorie HS ─────────────────────────────────
        migrations.AddField(
            model_name="elementvariable",
            name="categorie_hs",
            field=models.CharField(
                blank=True,
                choices=[
                    ("jour", "Heures sup de jour (25 %)"),
                    ("nuit", "Heures sup de nuit (50 %)"),
                    ("ferie", "Heures sup férié/dimanche (100 %)"),
                ],
                default="jour",
                max_length=6,
                verbose_name="Catégorie HS",
            ),
        ),
    ]
