"""SOLMVP — coquille de migrations de l'app « juridique ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app juridique`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate juridique 0007_ntjur12_budget_alloue`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('juridique', '0007_ntjur12_budget_alloue'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='Audience'),
                migrations.DeleteModel(name='DelaiPrescription'),
                migrations.DeleteModel(name='EtapeApprobationJuridique'),
                migrations.DeleteModel(name='NoteHonoraires'),
                migrations.DeleteModel(name='MandatAvocat'),
                migrations.DeleteModel(name='RegleApprobationJuridique'),
                migrations.DeleteModel(name='CabinetAvocat'),
                migrations.DeleteModel(name='DossierJuridique'),
            ],
            database_operations=[],
        ),
    ]
