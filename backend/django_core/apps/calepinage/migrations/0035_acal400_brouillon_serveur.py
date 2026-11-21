# ACAL400 — brouillons d'atelier côté serveur, par utilisateur (SCHEMA).
#
# Migration ADDITIVE : un champ JSON vide par défaut, aucune ligne réécrite.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0034_acon28_statut_refuse'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='brouillons_atelier',
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name="Brouillons d'atelier"),
        ),
    ]
