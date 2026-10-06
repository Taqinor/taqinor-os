"""CIQ215 — ``Facture.ventilation_tva`` : la TVA d'une facture de tranche
ventilée par taux (base 10 % / TVA 10 % / base 20 % / TVA 20 %).

ADDITIF : une colonne JSON nullable, aucun backfill, aucune facture existante
modifiée. Réversible : ``python manage.py migrate facturation 0010``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0010_ciq214_retenue_garantie'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='ventilation_tva',
            field=models.JSONField(
                blank=True, null=True,
                verbose_name='Ventilation TVA par taux'),
        ),
    ]
