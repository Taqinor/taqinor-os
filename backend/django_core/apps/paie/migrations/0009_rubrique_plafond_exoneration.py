# Generated manually — PAIE16 avantages en nature & indemnités
# imposables vs non-imposables (plafonds).
#
# Additive et réversible :
# * ``Rubrique`` : deux nouveaux champs —
#   - ``avantage_nature`` (BooleanField, défaut False) : distingue un avantage
#     en nature d'une indemnité en numéraire (informatif).
#   - ``plafond_exoneration`` (DecimalField nullable) : plafond mensuel
#     d'exonération d'une indemnité/avantage ; l'excédent au-delà du plafond est
#     réintégré dans la base imposable. ``None`` = comportement historique
#     (entièrement imposable ou exonéré selon le drapeau ``imposable``).

from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE16 — Avantages en nature & indemnités imposables/non-imposables.

    Ajoute le drapeau ``avantage_nature`` et le ``plafond_exoneration`` nullable
    sur ``Rubrique``. Migration purement additive, réversible : sans plafond
    renseigné, le calcul du bulletin est strictement identique à l'existant.
    """

    dependencies = [
        ("paie", "0008_anciennete_bareme"),
    ]

    operations = [
        migrations.AddField(
            model_name="rubrique",
            name="avantage_nature",
            field=models.BooleanField(
                default=False,
                verbose_name="Avantage en nature",
            ),
        ),
        migrations.AddField(
            model_name="rubrique",
            name="plafond_exoneration",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
                verbose_name="Plafond mensuel d'exonération",
            ),
        ),
    ]
