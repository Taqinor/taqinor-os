"""NTP2P21 — Suggestions de consolidation de commandes.

Additif pur : ``Fournisseur.frais_livraison_estimes`` (nullable), un champ
libre configurable qui sert UNIQUEMENT à chiffrer l'économie potentielle
d'une suggestion de fusion de bons de commande brouillon vers le même
fournisseur. Vide = aucun chiffrage proposé (jamais un montant inventé).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0143_ntp2p31_plafond_notes_frais_actif'),
    ]

    operations = [
        migrations.AddField(
            model_name='fournisseur',
            name='frais_livraison_estimes',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text='Estimation forfaitaire des frais de livraison '
                          'par commande chez ce fournisseur — sert '
                          "uniquement à chiffrer l'économie d'une "
                          'consolidation de bons de commande. Vide = aucun '
                          'chiffrage proposé.',
                verbose_name='Frais de livraison estimés (MAD/commande)'),
        ),
    ]
