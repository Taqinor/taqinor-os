# Fusion des deux branches de migrations facturation : la vague facturation
# (0015_afac32 → 0018_apar61) et ENF13 (0015_paiement_…_non_negatif) arrivées
# en parallèle sur main. Aucune opération.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0018_apar61_facture_identite_vendeur'),
        ('facturation', '0015_paiement_paiement_frais_rejet_non_negatif_and_more'),
    ]

    operations = []
