# ODX19 (suite) — re-pointe la FK CROSS-APP de compta vers apps.achats.
# ODX19 avait sorti BonCommandeFournisseur de stock vers achats (state-only,
# table stock_boncommandefournisseur inchangée) mais avait OUBLIÉ de
# re-pointer les FK-chaîne des AUTRES apps — d'où fields.E300/E307
# (« lazy reference to 'stock.boncommandefournisseur' »). Cette migration
# corrige compta.Rapprochement.bon_commande. State-only
# (SeparateDatabaseAndState, ZÉRO SQL) : la colonne physique `bon_commande_id`
# ne change pas, seule l'étiquette de modèle Django change côté état. Dépend
# d'achats 0001 (qui crée BonCommandeFournisseur dans l'état achats).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0110_xplt20_regle_intersociete'),
        ('achats', '0001_odx19_achats_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='rapprochement',
                    name='bon_commande',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='compta_rapprochements',
                        to='achats.boncommandefournisseur',
                        verbose_name='Bon de commande fournisseur'),
                ),
            ],
            database_operations=[],
        ),
    ]
