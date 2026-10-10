"""ATOT36 (C-AMET-004, D-ATOT5) — ``Avoir.type`` : correction |
geste_commercial | retour. Seuls les avoirs de CORRECTION sont remis au
solde de l'échéancier (décision fondateur 10/10/2026).

Deux étapes, ADDITIVES :
1. AddField à défaut ``correction`` : chaque avoir EXISTANT devient une
   correction — exactement le calcul d'hier (tout avoir était remis au
   solde), aucun chiffre existant ne bouge.
2. AlterField : défaut du modèle ``geste_commercial`` pour les NOUVEAUX
   avoirs (correction seulement si l'utilisateur la choisit).
Réversible : revenir à facturation 0020.
"""
from django.db import migrations, models

CHOIX = [('correction', 'Correction'),
         ('geste_commercial', 'Geste commercial'),
         ('retour', 'Retour')]


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0020_afac17_paiement_annule_saisie'),
    ]

    operations = [
        migrations.AddField(
            model_name='avoir',
            name='type',
            field=models.CharField(
                choices=CHOIX, default='correction', max_length=20),
        ),
        migrations.AlterField(
            model_name='avoir',
            name='type',
            field=models.CharField(
                choices=CHOIX, default='geste_commercial', max_length=20),
        ),
    ]
