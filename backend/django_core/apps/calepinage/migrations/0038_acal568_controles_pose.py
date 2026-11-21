# ACAL568 — les valeurs de pose déclarées par un système de fixation (SCHEMA).
#
# Migration ADDITIVE et réversible : une colonne JSON à objet vide par défaut
# (aucune ligne réécrite). Un système sans contrôle déclaré ne produit aucune
# alerte (D12).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0037_acal566_couvertures_fixation'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemefixation',
            name='controles_pose',
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name='Contrôles de pose'),
        ),
    ]
