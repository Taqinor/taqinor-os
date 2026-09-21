"""SOLMVP — coquille de migrations de l'app « voip ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app voip`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate voip 0001_initial`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('voip', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='Appel'),
                migrations.DeleteModel(name='VoipIdentifiantUtilisateur'),
                migrations.DeleteModel(name='VoipParametres'),
            ],
            database_operations=[],
        ),
    ]
