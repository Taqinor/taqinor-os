"""AUDV21 — nouvelle source ``flotte`` pour ``ElementVariable.source``.

Trace l'origine d'un élément importé depuis la flotte (avantage en nature
véhicule, ``services.importer_avantages_nature_flotte``) — même principe que
la source ``rh`` existante. Choix supplémentaire seulement : aucune donnée
existante n'est touchée (les valeurs ``manuel``/``rh`` restent inchangées).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0045_aud713_unicite_depot_bds_principal'),
    ]

    operations = [
        migrations.AlterField(
            model_name='elementvariable',
            name='source',
            field=models.CharField(
                choices=[
                    ('manuel', 'Saisie manuelle'),
                    ('rh', 'Import RH'),
                    ('flotte', 'Import flotte (avantage en nature)'),
                ],
                default='manuel',
                max_length=10,
                verbose_name='Source',
            ),
        ),
    ]
