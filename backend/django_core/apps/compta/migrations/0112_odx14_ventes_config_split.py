# ODX14 — sortie de la configuration de vente (FG209–221) de compta vers
# ``apps.ventes`` en STATE-ONLY : compta retire les modèles de l'état
# (SeparateDatabaseAndState, zéro SQL) AVANT que ventes 0085 ne les recrée dans
# l'état sur les MÊMES tables (db_table='compta_<model>'). Aucune donnée
# déplacée. Même recette que ODX9/ODX11/ODX12/ODX13.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0111_odx19_repoint_achats_crossapp'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # 1) Retirer d'abord toutes les FK (company + FK user + la FK
                # interne TranchePaiement→EcheancierPaiement).
                migrations.RemoveField(
                    model_name='codepromotion',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='modeledevis',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='sessionguidedselling',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='sessionguidedselling',
                    name='auteur',
                ),
                migrations.RemoveField(
                    model_name='demandeapprobationconfig',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='demandeapprobationconfig',
                    name='demandeur',
                ),
                migrations.RemoveField(
                    model_name='demandeapprobationconfig',
                    name='decideur',
                ),
                migrations.RemoveField(
                    model_name='ecatalogue',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='documentproposition',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='simulationpublique',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='simulationfinancement',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='offrefinancement',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='ligneincitation',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='echeancierpaiement',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='tranchepaiement',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='tranchepaiement',
                    name='echeancier',
                ),
                # 2) Puis supprimer les modèles de l'état compta (les
                # dépendants d'abord : TranchePaiement avant EcheancierPaiement).
                migrations.DeleteModel(
                    name='TranchePaiement',
                ),
                migrations.DeleteModel(
                    name='EcheancierPaiement',
                ),
                migrations.DeleteModel(
                    name='CodePromotion',
                ),
                migrations.DeleteModel(
                    name='ModeleDevis',
                ),
                migrations.DeleteModel(
                    name='SessionGuidedSelling',
                ),
                migrations.DeleteModel(
                    name='DemandeApprobationConfig',
                ),
                migrations.DeleteModel(
                    name='ECatalogue',
                ),
                migrations.DeleteModel(
                    name='DocumentProposition',
                ),
                migrations.DeleteModel(
                    name='SimulationPublique',
                ),
                migrations.DeleteModel(
                    name='SimulationFinancement',
                ),
                migrations.DeleteModel(
                    name='OffreFinancement',
                ),
                migrations.DeleteModel(
                    name='LigneIncitation',
                ),
            ],
            database_operations=[],
        ),
    ]
