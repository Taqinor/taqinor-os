# ODX19 (suite) — re-pointe la FK CROSS-APP de ventes vers apps.achats.
# ODX19 avait sorti BonCommandeFournisseur/FactureFournisseur/… de stock vers
# achats (state-only, tables stock_* inchangées) mais avait OUBLIÉ de
# re-pointer les FK-chaîne des AUTRES apps qui les référencent — d'où des
# fields.E300/E307 (« lazy reference to 'stock.boncommandefournisseur' »).
# Cette migration corrige ventes.ShareLink.bon_commande_fournisseur.
# State-only (SeparateDatabaseAndState, ZÉRO SQL) : la colonne physique
# `bon_commande_fournisseur_id` et sa table ne changent pas, seule l'étiquette
# de modèle Django change côté état. Dépend d'achats 0001 (qui crée
# BonCommandeFournisseur dans l'état achats, sur la table stock_* inchangée).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0083_odx17_facturation_split'),
        ('achats', '0001_odx19_achats_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='sharelink',
                    name='bon_commande_fournisseur',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='share_links',
                        to='achats.boncommandefournisseur'),
                ),
            ],
            database_operations=[],
        ),
    ]
