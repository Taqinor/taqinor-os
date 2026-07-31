"""Archivage fournisseur — `Fournisseur.is_archived` (même patron que
`Produit.is_archived`).

Additif et réversible : un booléen `default=False` (aucun fournisseur
existant n'est archivé, comportement API strictement inchangé). Le repli
d'archivage de `FournisseurViewSet.destroy` s'appuie dessus quand la
suppression est refusée par le PROTECT posé sur `achats.PrixFournisseur`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0081_protect_produit_donnees_reelles'),
    ]

    operations = [
        migrations.AddField(
            model_name='fournisseur',
            name='is_archived',
            field=models.BooleanField(
                default=False,
                help_text="Fournisseur archivé : masqué des listes, ses prix "
                          "d'achat et son historique sont conservés.",
                verbose_name='Archivé',
            ),
        ),
    ]
