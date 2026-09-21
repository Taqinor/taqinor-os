"""SOLMVP — coquille de migrations de l'app « mrp ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app mrp`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate mrp 0016_ntmfg32_echeance_entretien_notifie`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mrp', '0016_ntmfg32_echeance_entretien_notifie'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CoutStandard'),
                migrations.DeleteModel(name='EcheanceEntretienPoste'),
                migrations.DeleteModel(name='OrdreModification'),
                migrations.DeleteModel(name='ParametresMRP'),
                migrations.DeleteModel(name='PauseOperationOF'),
                migrations.DeleteModel(name='ReglesKanbanProduction'),
                migrations.DeleteModel(name='ReservationOF'),
                migrations.DeleteModel(name='OperationOF'),
                migrations.DeleteModel(name='PlanEntretienPoste'),
                migrations.DeleteModel(name='OperationGamme'),
                migrations.DeleteModel(name='OrdreFabrication'),
                migrations.DeleteModel(name='Gamme'),
                migrations.DeleteModel(name='PosteDeCharge'),
            ],
            database_operations=[],
        ),
    ]
