"""NTWMS3 — stratégie de prélèvement par défaut sur la catégorie produit.

Additif et réversible : colonne à valeur par défaut ``aucune``, qui reproduit
EXACTEMENT le comportement historique (le prélèvement ne consulte ni lot ni
casier). Aucun backfill, aucune donnée touchée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0085_ntadm2_produit_entite'),
    ]

    operations = [
        migrations.AddField(
            model_name='categorie',
            name='strategie_picking_defaut',
            field=models.CharField(
                choices=[
                    ('aucune', 'Aucune (comportement historique)'),
                    ('fifo', 'FIFO — premier entré, premier sorti'),
                    ('fefo', "FEFO — péremption la plus proche d'abord"),
                    ('zone', 'Zone — casier le plus proche de la sortie'),
                ],
                default='aucune',
                help_text='NTWMS3 — stratégie de prélèvement des produits de '
                          'cette catégorie. « Aucune » (défaut) = '
                          'comportement historique.',
                max_length=10),
        ),
    ]
