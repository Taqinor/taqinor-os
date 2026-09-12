# VTA2 — sortie de la visite technique terrain (VisiteTerrain/VisiteMedia) de
# ``apps.crm`` vers ``apps.visites`` en STATE-ONLY : crm retire les modèles de
# l'état (SeparateDatabaseAndState, ZÉRO SQL) AVANT que ``visites.0001`` ne les
# recrée dans l'état sur les MÊMES tables (db_table='crm_visiteterrain' /
# 'crm_visitemedia'). Aucune donnée déplacée, aucun index recréé.
#
# L'ORDRE compte : les FK partent d'abord (RemoveField), les modèles ensuite
# (DeleteModel) — sinon Django refuserait de supprimer un modèle encore
# référencé. Et la migration ``visites.0001`` DÉPEND de celle-ci : aucun
# instant de la chaîne n'a donc deux modèles pour la même table.
#
# Même recette qu'ODX11 (apps/compta/migrations/0106 ↔ apps/ao/0001).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0098_ckp2_cadence_depart'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # 0) Retirer d'abord les INDEX de l'état : ils portent sur des
                # champs qu'on s'apprête à retirer, et un index d'état qui
                # référence un champ absent est un état incohérent. Aucun SQL :
                # les index physiques `crm_vterr_*` / `crm_vmedia_*` restent en
                # base, et `visites.0001` les redéclare sous les MÊMES noms.
                migrations.RemoveIndex(
                    model_name='visiteterrain',
                    name='crm_vterr_comp_statut_idx',
                ),
                migrations.RemoveIndex(
                    model_name='visiteterrain',
                    name='crm_vterr_comp_com_idx',
                ),
                migrations.RemoveIndex(
                    model_name='visitemedia',
                    name='crm_vmedia_visite_slot_idx',
                ),
                # 1) Puis toutes les FK (company + inter-modèles).
                migrations.RemoveField(
                    model_name='visitemedia',
                    name='attachment',
                ),
                migrations.RemoveField(
                    model_name='visitemedia',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='visitemedia',
                    name='visite',
                ),
                migrations.RemoveField(
                    model_name='visiteterrain',
                    name='commercial',
                ),
                migrations.RemoveField(
                    model_name='visiteterrain',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='visiteterrain',
                    name='lead',
                ),
                # 2) Puis supprimer les modèles de l'état crm.
                migrations.DeleteModel(
                    name='VisiteMedia',
                ),
                migrations.DeleteModel(
                    name='VisiteTerrain',
                ),
            ],
            database_operations=[],
        ),
    ]
