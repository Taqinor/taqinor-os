"""CAL139 — les POSTES DE PERTES, explicites et sourcés, sur le calepinage.

ADDITIVE et SANS DÉFAUT MÉTIER : la colonne naît à ``[]`` pour tout le monde,
et une liste vide veut dire « aucune perte renseignée » — donc aucune
simulation, jamais un 14 % ou un 20 % implicite. Un calepinage existant se
comporte donc EXACTEMENT comme avant cette migration.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0004_cal130_norme_electrique'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='pertes',
            field=models.JSONField(blank=True, default=list,
                                   verbose_name='Postes de pertes'),
        ),
    ]
