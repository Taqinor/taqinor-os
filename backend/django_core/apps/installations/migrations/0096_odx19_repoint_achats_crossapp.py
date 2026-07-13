# ODX19 (suite) — re-pointe les FK CROSS-APP d'installations vers apps.achats.
# ODX19 avait sorti BonCommandeFournisseur/FactureFournisseur/
# ReceptionFournisseur de stock vers achats (state-only, tables stock_*
# inchangées) mais avait OUBLIÉ de re-pointer les FK-chaîne des AUTRES apps
# qui les référencent — d'où des fields.E300/E307 (« lazy reference to
# 'stock.boncommandefournisseur'/'stock.facturefournisseur'/
# 'stock.receptionfournisseur' »). Cette migration corrige les FK de
# DemandeAchat, RFQ, ApprobationBCF, BudgetEngagement, ReceptionNonFacturee et
# DossierImport. State-only (SeparateDatabaseAndState, ZÉRO SQL) : les colonnes
# physiques `*_id` et leurs tables ne changent pas, seule l'étiquette de modèle
# Django change côté état. Dépend d'achats 0001 (qui crée les modèles dans
# l'état achats, sur les tables stock_* inchangées) ; achats 0001 dépend
# lui-même d'installations 0095, il n'y a donc pas de cycle.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0095_sca36_demandeachat_kit'),
        ('achats', '0001_odx19_achats_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='demandeachat',
                    name='bon_commande',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='installations_demandes_achat',
                        to='achats.boncommandefournisseur'),
                ),
                migrations.AlterField(
                    model_name='rfq',
                    name='bon_commande',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='installations_rfqs',
                        to='achats.boncommandefournisseur'),
                ),
                migrations.AlterField(
                    model_name='approbationbcf',
                    name='bcf',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='installations_approbations',
                        to='achats.boncommandefournisseur'),
                ),
                migrations.AlterField(
                    model_name='budgetengagement',
                    name='bon_commande',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='installations_budget_engagements',
                        to='achats.boncommandefournisseur'),
                ),
                migrations.AlterField(
                    model_name='budgetengagement',
                    name='facture',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='installations_budget_engagements',
                        to='achats.facturefournisseur'),
                ),
                migrations.AlterField(
                    model_name='receptionnonfacturee',
                    name='reception',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='installations_gr_ir',
                        to='achats.receptionfournisseur'),
                ),
                migrations.AlterField(
                    model_name='receptionnonfacturee',
                    name='bon_commande',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='installations_gr_ir',
                        to='achats.boncommandefournisseur'),
                ),
                migrations.AlterField(
                    model_name='receptionnonfacturee',
                    name='facture',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='installations_gr_ir',
                        to='achats.facturefournisseur'),
                ),
                migrations.AlterField(
                    model_name='dossierimport',
                    name='bon_commande',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='installations_dossiers_import',
                        to='achats.boncommandefournisseur'),
                ),
            ],
            database_operations=[],
        ),
    ]
