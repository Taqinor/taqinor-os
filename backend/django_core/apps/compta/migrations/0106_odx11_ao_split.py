# ODX11 — sortie des appels d'offres (FG222–227) de compta vers ``apps.ao`` en
# STATE-ONLY : compta retire les modèles de l'état (SeparateDatabaseAndState,
# zéro SQL) AVANT que ao 0001 ne les recrée dans l'état sur les MÊMES tables
# (db_table='compta_<model>'). Aucune donnée déplacée.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0105_odx16_abonnement_monitoring_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # 1) Retirer d'abord toutes les FK (company + FK inter-modèles).
                migrations.RemoveField(
                    model_name='appeloffre',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='bordereauprix',
                    name='appel_offre',
                ),
                migrations.RemoveField(
                    model_name='bordereauprix',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='lignebordereau',
                    name='bordereau',
                ),
                migrations.RemoveField(
                    model_name='lignebordereau',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='cautionsoumission',
                    name='appel_offre',
                ),
                migrations.RemoveField(
                    model_name='cautionsoumission',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='dossiersoumission',
                    name='appel_offre',
                ),
                migrations.RemoveField(
                    model_name='dossiersoumission',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='piecesoumission',
                    name='dossier',
                ),
                migrations.RemoveField(
                    model_name='piecesoumission',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='echeanceao',
                    name='appel_offre',
                ),
                migrations.RemoveField(
                    model_name='echeanceao',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='resultatao',
                    name='appel_offre',
                ),
                migrations.RemoveField(
                    model_name='resultatao',
                    name='company',
                ),
                # 2) Puis supprimer les modèles de l'état compta.
                migrations.DeleteModel(
                    name='ResultatAO',
                ),
                migrations.DeleteModel(
                    name='EcheanceAO',
                ),
                migrations.DeleteModel(
                    name='PieceSoumission',
                ),
                migrations.DeleteModel(
                    name='DossierSoumission',
                ),
                migrations.DeleteModel(
                    name='CautionSoumission',
                ),
                migrations.DeleteModel(
                    name='LigneBordereau',
                ),
                migrations.DeleteModel(
                    name='BordereauPrix',
                ),
                migrations.DeleteModel(
                    name='AppelOffre',
                ),
            ],
            database_operations=[],
        ),
    ]
