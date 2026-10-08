"""ATOT6 — ``NoteDebit.ventilation_tva`` : ventilation TVA par taux recopiée
au prorata de la facture d'origine (tranche à taux mixtes, CIQ215).

ADDITIF : une colonne JSON nullable, aucune note existante modifiée.
Réversible : revenir à ventes 0132.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0132_acal102_backfill_production_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='notedebit',
            name='ventilation_tva',
            field=models.JSONField(
                blank=True, null=True,
                verbose_name='Ventilation TVA par taux'),
        ),
    ]
