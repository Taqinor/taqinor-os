"""SOLMVP — coquille de migrations de l'app « scm ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app scm`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate scm 0012_ntscm45_parametresscm_seuil_alerte_mape`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scm', '0012_ntscm45_parametresscm_seuil_alerte_mape'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ClassificationABC'),
                migrations.DeleteModel(name='EvenementDemande'),
                migrations.DeleteModel(name='LigneDemandeSOP'),
                migrations.DeleteModel(name='LigneOffreSOP'),
                migrations.DeleteModel(name='ParametresSCM'),
                migrations.DeleteModel(name='PolitiqueStock'),
                migrations.DeleteModel(name='PrevisionDemande'),
                migrations.DeleteModel(name='CyclePlanificationSOP'),
            ],
            database_operations=[],
        ),
    ]
