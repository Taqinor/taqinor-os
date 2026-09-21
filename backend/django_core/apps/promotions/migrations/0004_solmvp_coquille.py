"""SOLMVP — coquille de migrations de l'app « promotions ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app promotions`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate promotions 0003_ntret15_cartecadeau`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('promotions', '0003_ntret15_cartecadeau'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CarteCadeau'),
                migrations.DeleteModel(name='CouponUtilisation'),
                migrations.DeleteModel(name='CouponUnique'),
                migrations.DeleteModel(name='ReglexPromotion'),
            ],
            database_operations=[],
        ),
    ]
