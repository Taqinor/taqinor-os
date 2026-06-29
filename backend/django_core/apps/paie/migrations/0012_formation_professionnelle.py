# Generated manually — PAIE24 taxe de formation professionnelle (charge patronale).
#
# Additive et réversible. Le taux ``ParametrePaie.taux_formation_pro`` (défaut
# 1,6 %) existe déjà depuis ``0001_initial`` : seul le champ de snapshot du
# bulletin est ajouté ici.
# * ``BulletinPaie.formation_professionnelle`` (DecimalField, défaut 0) : montant
#   patronal de la taxe de formation professionnelle (1,6 % du brut, collectée
#   avec la CNSS) figé au snapshot du bulletin. Charge employeur informative —
#   jamais déduite du net du salarié.

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """PAIE24 — Taxe de formation professionnelle (charge patronale informative).

    Ajoute le champ de snapshot ``formation_professionnelle`` sur
    ``BulletinPaie``. Migration purement additive et réversible : sans valeur
    renseignée, le calcul du bulletin reste cohérent (taux 1,6 % par défaut,
    charge 100 % patronale qui ne touche pas le net).
    """

    dependencies = [
        ("paie", "0011_allocations_familiales"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulletinpaie",
            name="formation_professionnelle",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=14,
                verbose_name="Formation professionnelle (patronal)",
            ),
        ),
    ]
