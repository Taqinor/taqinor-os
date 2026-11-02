"""AARG27 (C-AARG-021) — ``Facture.identite_acheteur`` : identité de l'acheteur
figée à l'émission, source du PDF et de l'UBL d'une facture émise.

ADDITIF : un ``JSONField`` nullable, aucune facture existante modifiée (sans
instantané, le rendu lit le client comme avant). Réversible : revenir à
facturation 0027.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0027_aarg24_niveaux_relance_defaut'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='identite_acheteur',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
