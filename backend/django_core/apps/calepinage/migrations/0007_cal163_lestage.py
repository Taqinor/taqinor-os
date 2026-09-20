"""CAL163 — la section « lestage » des réglages société (paramètres SAISIS).

ADDITIVE et SANS DONNÉE : le champ naît à ``{}`` pour toutes les sociétés.
Une section vide veut dire « aucun paramètre saisi », donc AUCUN résultat de
lestage calculé — exactement le comportement d'aujourd'hui (le module ne
calculait aucune charge de vent/neige). Aucune société existante ne change
donc de comportement en recevant ce champ.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0006_cal149_profils_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametrescalepinage',
            name='lestage',
            field=models.JSONField(blank=True, default=dict,
                                   verbose_name='Paramètres de lestage'),
        ),
    ]
