"""SOLMVP — coquille de migrations de l'app « conversation_ai ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app conversation_ai`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate conversation_ai 0002_ntai22_analyse`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('conversation_ai', '0002_ntai22_analyse'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AppelCommercial'),
            ],
            database_operations=[],
        ),
    ]
