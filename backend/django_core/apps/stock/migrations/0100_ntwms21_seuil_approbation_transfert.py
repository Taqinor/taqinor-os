"""NTWMS21 — seuil d'approbation des transferts de valeur.

Additive et neutre : 0 par défaut = garde DÉSACTIVÉE, le transfert direct
historique reste strictement inchangé pour toutes les sociétés existantes.
Le workflow demande → approbation → exécution n'est PAS recréé ici : il
existe déjà (``installations.DemandeTransfert``, FG325).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0099_ntwms20_portail_tiers'),
    ]

    operations = [
        migrations.AddField(
            model_name='achatsparametres',
            name='seuil_approbation_transfert',
            field=models.DecimalField(
                decimal_places=2, default=0,
                help_text='NTWMS21 — valeur MAD au-dessus de laquelle un '
                          'transfert exige une approbation. 0 = désactivé.',
                max_digits=14),
        ),
    ]
