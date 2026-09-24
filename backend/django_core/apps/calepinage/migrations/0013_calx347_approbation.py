"""CALX347 — la décision d'approbation d'un calepinage, dans SON champ.

ADDITIVE et SANS DONNÉE : le champ naît à ``NULL`` pour tous les calepinages
existants, ce qui veut dire « personne n'a encore décidé » — exactement l'état
d'aujourd'hui (D12). La décision ne vit jamais dans ``resultat`` (qui
appartient au moteur et qu'une simulation réécrit).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0012_calx307_sections_rapport'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='approbation',
            field=models.JSONField(blank=True, default=None, null=True,
                                   verbose_name='Approbation'),
        ),
    ]
