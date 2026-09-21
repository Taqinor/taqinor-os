"""SOLMVP — coquille de migrations de l'app « agriculture ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app agriculture`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate agriculture 0006_lotrecolte`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agriculture', '0006_lotrecolte'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='EtapeCampagne'),
                migrations.DeleteModel(name='LotRecolte'),
                migrations.DeleteModel(name='PointageAgricole'),
                migrations.DeleteModel(name='RelevePointIrrigation'),
                migrations.DeleteModel(name='UtilisationMateriel'),
                migrations.DeleteModel(name='CampagneCulturale'),
                migrations.DeleteModel(name='EquipeSaisonniere'),
                migrations.DeleteModel(name='IntrantAgricole'),
                migrations.DeleteModel(name='MaterielAgricole'),
                migrations.DeleteModel(name='PointIrrigation'),
                migrations.DeleteModel(name='Parcelle'),
                migrations.DeleteModel(name='Exploitation'),
            ],
            database_operations=[],
        ),
    ]
