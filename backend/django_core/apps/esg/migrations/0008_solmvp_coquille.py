"""SOLMVP — coquille de migrations de l'app « esg ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app esg`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate esg 0007_ntesg20_parametres_esg`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('esg', '0007_ntesg20_parametres_esg'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CatalogueIndicateurESG'),
                migrations.DeleteModel(name='DocumentPolitiqueESG'),
                migrations.DeleteModel(name='FacteurEmissionReference'),
                migrations.DeleteModel(name='FacteurEmissionVersionCounter'),
                migrations.DeleteModel(name='ObjectifESGTrajectoire'),
                migrations.DeleteModel(name='ParametresESG'),
                migrations.DeleteModel(name='PartiePrenanteESG'),
                migrations.DeleteModel(name='SnapshotESG'),
                migrations.DeleteModel(name='PeriodeReportingESG'),
            ],
            database_operations=[],
        ),
    ]
