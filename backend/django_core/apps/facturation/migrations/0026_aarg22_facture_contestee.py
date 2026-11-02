"""AARG22 (D-AFAC-89 a) — ``Facture.contestee_le`` + ``motif_contestation``.

Deux colonnes additives (date NULL, texte vide par défaut) : une facture
contestée sort de toute relance (``recouvrement.facture_relancable``).
Réversible : revenir à facturation 0025 retire les colonnes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0025_amet4_facture_acompte_auto_le'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='contestee_le',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='facture',
            name='motif_contestation',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
