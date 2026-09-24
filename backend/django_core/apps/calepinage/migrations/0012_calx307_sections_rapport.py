"""CALX307 — la société choisit les sections incluses dans ses rapports.

ADDITIVE et SANS DONNÉE : le champ naît à ``{}`` pour toutes les sociétés.
Une section vide veut dire « rien de réglé », donc TOUTES les sections
déclarées par ``rapport_etude.json`` s'impriment — c'est exactement le
comportement d'aujourd'hui (D12) : aucune société existante ne change de
rapport en recevant ce champ.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0011_calx258_profils_segments'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrescalepinage',
            name='documents',
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name='Documents'),
        ),
    ]
