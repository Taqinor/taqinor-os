"""APDF30 (C-APDF-011) — ``Paiement.numero_recu`` : numéro du reçu, séquence
propre à la société, unique par société quand renseigné.

ADDITIF : une colonne texte défaut vide + une contrainte partielle (le vide
est exclu) ; aucun paiement existant modifié. Réversible : revenir à
facturation 0016.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0016_afac46_relance_compte_dans_cadence'),
    ]

    operations = [
        migrations.AddField(
            model_name='paiement',
            name='numero_recu',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddConstraint(
            model_name='paiement',
            constraint=models.UniqueConstraint(
                condition=models.Q(('numero_recu', ''), _negated=True),
                fields=('company', 'numero_recu'),
                name='uniq_paiement_numero_recu_par_societe'),
        ),
    ]
