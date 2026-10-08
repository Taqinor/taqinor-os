"""ATOT6 — ``Avoir.ventilation_tva`` : ventilation TVA par taux recopiée au
prorata de la facture d'origine (tranche à taux mixtes, CIQ215).

ADDITIF : une colonne JSON nullable, aucun avoir existant modifié.
Réversible : revenir à facturation 0013.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0013_atot5_cle_tranche'),
    ]

    operations = [
        migrations.AddField(
            model_name='avoir',
            name='ventilation_tva',
            field=models.JSONField(
                blank=True, null=True,
                verbose_name='Ventilation TVA par taux'),
        ),
    ]
