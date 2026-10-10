"""ATOT36 (C-AMET-004, D-ATOT5) — ``Avoir.type`` : correction |
geste_commercial | retour. Seuls les avoirs de CORRECTION réduisent le solde
de l'échéancier (décision fondateur 10/10/2026).

ADDITIF : une colonne à défaut ``geste_commercial`` — le type NEUTRE pour la
dernière tranche (l'avoir ne réduit que le dû de sa facture, jamais le
solde) : aucun avoir existant ne fait baisser après coup une tranche restant
à générer. Réversible : revenir à facturation 0020.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0020_afac17_paiement_annule_saisie'),
    ]

    operations = [
        migrations.AddField(
            model_name='avoir',
            name='type',
            field=models.CharField(
                choices=[('correction', 'Correction'),
                         ('geste_commercial', 'Geste commercial'),
                         ('retour', 'Retour')],
                default='geste_commercial', max_length=20),
        ),
    ]
