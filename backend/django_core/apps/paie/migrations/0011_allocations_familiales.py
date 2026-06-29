# Generated manually — PAIE23 allocations familiales (charge patronale).
#
# Additive et réversible :
# * ``ParametrePaie.taux_allocations_familiales`` (DecimalField, défaut 6.4) :
#   taux patronal des allocations familiales (prestations familiales CNSS),
#   non plafonné, éditable par société.
# * ``BulletinPaie.allocations_familiales`` (DecimalField, défaut 0) : montant
#   patronal figé au snapshot du bulletin. Charge employeur informative — jamais
#   déduite du net du salarié.

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE23 — Allocations familiales (charge patronale informative).

    Ajoute le taux patronal des allocations familiales sur ``ParametrePaie``
    (défaut 6,4 %) et le champ de snapshot ``allocations_familiales`` sur
    ``BulletinPaie``. Migration purement additive et réversible : sans valeur
    renseignée, le calcul du bulletin reste cohérent (taux 6,4 % par défaut,
    charge 100 % patronale qui ne touche pas le net).
    """

    dependencies = [
        ("paie", "0010_bulletinpaie_lignebulletin"),
    ]

    operations = [
        migrations.AddField(
            model_name="parametrepaie",
            name="taux_allocations_familiales",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("6.4"),
                max_digits=6,
                verbose_name="Taux allocations familiales (patronal)",
            ),
        ),
        migrations.AddField(
            model_name="bulletinpaie",
            name="allocations_familiales",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=14,
                verbose_name="Allocations familiales (patronal)",
            ),
        ),
    ]
