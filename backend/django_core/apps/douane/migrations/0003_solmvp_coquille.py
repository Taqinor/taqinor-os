"""SOLMVP — coquille de migrations de l'app « douane ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app douane`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate douane 0002_ntlog36_parametresdouane`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('douane', '0002_ntlog36_parametresdouane'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ParametresDouane'),
                migrations.DeleteModel(name='PieceDossierExport'),
                migrations.DeleteModel(name='DossierExport'),
            ],
            database_operations=[],
        ),
    ]
