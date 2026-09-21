"""SOLMVP — coquille de migrations de l'app « frais ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app frais`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate frais 0005_cht16_indemnite_chantier_installation_id`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('frais', '0005_cht16_indemnite_chantier_installation_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='IndemniteChantier'),
                migrations.DeleteModel(name='NoteFrais'),
                migrations.DeleteModel(name='PlafondNoteFrais'),
                migrations.DeleteModel(name='BaremeIndemnite'),
                migrations.DeleteModel(name='RapportNoteFrais'),
            ],
            database_operations=[],
        ),
    ]
