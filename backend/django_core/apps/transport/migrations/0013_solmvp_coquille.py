"""SOLMVP — coquille de migrations de l'app « transport ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app transport`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate transport 0012_ordretransport_archive_and_more`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('transport', '0012_ordretransport_archive_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CoutFretReel'),
                migrations.DeleteModel(name='FacteurEmissionCO2'),
                migrations.DeleteModel(name='LigneOrdreTransport'),
                migrations.DeleteModel(name='ParametresTransport'),
                migrations.DeleteModel(name='ReserveReception'),
                migrations.DeleteModel(name='EtapeTransport'),
                migrations.DeleteModel(name='LitigeTransport'),
                migrations.DeleteModel(name='OrdreTransport'),
            ],
            database_operations=[],
        ),
    ]
