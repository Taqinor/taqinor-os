"""SOLMVP — coquille de migrations de l'app « dataquality ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app dataquality`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate dataquality 0005_ntdata20_propositionfusion`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dataquality', '0005_ntdata20_propositionfusion'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='GoldenRecord'),
                migrations.DeleteModel(name='PropositionFusion'),
                migrations.DeleteModel(name='RegleSurvivorship'),
                migrations.DeleteModel(name='ResultatQualite'),
                migrations.DeleteModel(name='RegleQualite'),
            ],
            database_operations=[],
        ),
    ]
