# ODX13 — sortie des partenaires/territoires (FG234–237) de compta vers
# ``apps.crm`` en STATE-ONLY : compta retire les modèles de l'état
# (SeparateDatabaseAndState, zéro SQL) AVANT que crm 0059 ne les recrée dans
# l'état sur les MÊMES tables (db_table='compta_<model>'). Aucune donnée
# déplacée. Même recette que ODX9/ODX11/ODX12.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0108_partenaire_tiers'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # 1) Retirer d'abord toutes les FK (company + FK inter-modèles
                # + la FK ARC19 vers tiers.Tiers).
                migrations.RemoveField(
                    model_name='partenaire',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='partenaire',
                    name='tiers',
                ),
                migrations.RemoveField(
                    model_name='soumissionleadpartenaire',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='soumissionleadpartenaire',
                    name='partenaire',
                ),
                migrations.RemoveField(
                    model_name='commissionpartenaire',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='commissionpartenaire',
                    name='partenaire',
                ),
                migrations.RemoveField(
                    model_name='territoirecommercial',
                    name='company',
                ),
                # 2) Puis supprimer les modèles de l'état compta.
                migrations.DeleteModel(
                    name='SoumissionLeadPartenaire',
                ),
                migrations.DeleteModel(
                    name='CommissionPartenaire',
                ),
                migrations.DeleteModel(
                    name='TerritoireCommercial',
                ),
                migrations.DeleteModel(
                    name='Partenaire',
                ),
            ],
            database_operations=[],
        ),
    ]
