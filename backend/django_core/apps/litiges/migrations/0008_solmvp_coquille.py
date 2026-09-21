"""SOLMVP — coquille de migrations de l'app « litiges ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app litiges`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate litiges 0007_ntjur6_dossier_juridique`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('litiges', '0007_ntjur6_dossier_juridique'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ReclamationActivity'),
                migrations.DeleteModel(name='Reclamation'),
            ],
            database_operations=[],
        ),
    ]
