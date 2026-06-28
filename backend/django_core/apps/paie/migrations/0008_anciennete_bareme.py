# Generated manually — PAIE15 prime d'ancienneté barème.
#
# Additive et réversible :
# * ``ParametrePaie`` : dix nouveaux champs (5 seuils en années + 5 taux %)
#   pour le barème d'ancienneté marocain standard (2/5/12/20/25 ans →
#   5/10/15/20/25 %). Tous éditables par société, valeurs par défaut légales.

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE15 — Prime d'ancienneté barème (5/10/15/20/25 %).

    Ajoute les 5 seuils d'ancienneté (en années) et leurs taux (%) éditables
    sur ``ParametrePaie``. Migration purement additive, réversible.
    """

    dependencies = [
        ("paie", "0007_hs_majoration"),
    ]

    operations = [
        # ── Seuil 1 : 2 ans → 5 % ──────────────────────────────────────────
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_seuil_1",
            field=models.PositiveSmallIntegerField(
                default=2,
                verbose_name="Ancienneté seuil 1 (années)",
            ),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_taux_1",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("5"),
                max_digits=6,
                verbose_name="Taux ancienneté seuil 1 (%)",
            ),
        ),
        # ── Seuil 2 : 5 ans → 10 % ─────────────────────────────────────────
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_seuil_2",
            field=models.PositiveSmallIntegerField(
                default=5,
                verbose_name="Ancienneté seuil 2 (années)",
            ),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_taux_2",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("10"),
                max_digits=6,
                verbose_name="Taux ancienneté seuil 2 (%)",
            ),
        ),
        # ── Seuil 3 : 12 ans → 15 % ────────────────────────────────────────
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_seuil_3",
            field=models.PositiveSmallIntegerField(
                default=12,
                verbose_name="Ancienneté seuil 3 (années)",
            ),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_taux_3",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("15"),
                max_digits=6,
                verbose_name="Taux ancienneté seuil 3 (%)",
            ),
        ),
        # ── Seuil 4 : 20 ans → 20 % ────────────────────────────────────────
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_seuil_4",
            field=models.PositiveSmallIntegerField(
                default=20,
                verbose_name="Ancienneté seuil 4 (années)",
            ),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_taux_4",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("20"),
                max_digits=6,
                verbose_name="Taux ancienneté seuil 4 (%)",
            ),
        ),
        # ── Seuil 5 : 25 ans → 25 % ────────────────────────────────────────
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_seuil_5",
            field=models.PositiveSmallIntegerField(
                default=25,
                verbose_name="Ancienneté seuil 5 (années)",
            ),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="anciennete_taux_5",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("25"),
                max_digits=6,
                verbose_name="Taux ancienneté seuil 5 (%)",
            ),
        ),
    ]
