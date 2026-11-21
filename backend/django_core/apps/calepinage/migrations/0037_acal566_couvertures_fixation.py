# ACAL566 — les couvertures servies par un système de fixation (SCHEMA).
#
# Migration ADDITIVE et réversible : une colonne JSON à liste vide par défaut
# (aucune ligne réécrite). Un système sans couverture déclarée garde le
# comportement d'aujourd'hui (D12).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0036_acal895_calepinage_exemple'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemefixation',
            name='couvertures',
            field=models.JSONField(blank=True, default=list,
                                   verbose_name='Couvertures servies'),
        ),
    ]
