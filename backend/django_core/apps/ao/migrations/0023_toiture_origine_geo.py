"""PV57 — l'ANCRE géographique du repère local d'une toiture.

Purement ADDITIVE et réversible : deux colonnes NULLABLES sur une table
existante, sans défaut et sans contrainte — aucune réécriture de ligne, aucun
verrou long. ``NULL`` est la valeur juste pour une toiture saisie sur plan
papier : un ``0.0`` désignerait le golfe de Guinée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0022_zone_toiture'),
    ]

    operations = [
        migrations.AddField(
            model_name='toitureao',
            name='origine_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name="Latitude de l'origine du repère local (°)"),
        ),
        migrations.AddField(
            model_name='toitureao',
            name='origine_lng',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True, verbose_name="Longitude de l'origine du repère local (°)"),
        ),
    ]
