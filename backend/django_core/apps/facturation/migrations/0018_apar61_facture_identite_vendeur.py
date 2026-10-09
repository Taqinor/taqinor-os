"""APAR61 (C-APAR-013, D-APAR-4) — ``Facture.identite_vendeur`` : identité
vendeur figée à l'émission, source du rendu PDF d'une facture émise.

ADDITIF : un ``JSONField`` nullable, aucune facture existante modifiée (sans
instantané, le PDF se rend depuis le profil vivant comme avant). Réversible :
revenir à facturation 0017.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0017_apdf30_paiement_numero_recu'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='identite_vendeur',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
