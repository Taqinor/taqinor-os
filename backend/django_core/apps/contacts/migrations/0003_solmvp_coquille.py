"""SOLMVP — coquille de migrations de l'app « contacts ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app contacts`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate contacts 0002_aud608_uniq_contact_principal`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0002_aud608_uniq_contact_principal'),
        ('contrats', '0058_solmvp_coquille'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ContactClient'),
            ],
            database_operations=[],
        ),
    ]
