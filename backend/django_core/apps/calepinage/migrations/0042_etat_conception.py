"""ACAL1006 — l'état de conception d'un calepinage (``rapide`` | ``complet``).

Additive et réversible : une colonne neuve, ``complet`` pour tout l'existant.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0041_acal887_production_mesuree'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinage',
            name='etat_conception',
            field=models.CharField(
                choices=[('rapide', 'Rapide'), ('complet', 'Complet')],
                default='complet', max_length=10,
                verbose_name='État de conception'),
        ),
    ]
