"""CIQ214 — retenue de garantie CLIENT sur une facture de tranche :
``Facture.retenue_garantie_mad`` (retenue sur le règlement, sans effet sur la
base taxable) et ``retenue_liberee_le`` (réception définitive).

ADDITIF : deux colonnes nullables, aucun backfill, aucune facture existante
modifiée. Réversible : ``python manage.py migrate facturation 0009``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0009_arrondi100_palier'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='retenue_garantie_mad',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name='Retenue de garantie (MAD)'),
        ),
        migrations.AddField(
            model_name='facture',
            name='retenue_liberee_le',
            field=models.DateField(
                blank=True, null=True, verbose_name='Retenue libérée le'),
        ),
    ]
