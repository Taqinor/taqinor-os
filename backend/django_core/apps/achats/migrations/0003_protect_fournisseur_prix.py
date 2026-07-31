"""`PrixFournisseur.fournisseur` : CASCADE -> PROTECT.

Symétrique de `0002_protect_produit_donnees_reelles` (côté produit) : le
tarif fournisseur porte un prix d'achat NÉGOCIÉ saisi à la main. Tant qu'il
existe, la suppression du fournisseur est refusée par le collecteur Django
au lieu d'effacer silencieusement toute sa grille de prix.

`on_delete` est un attribut NON-DB (`django.db.models.Field.non_db_attrs`) :
cette `AlterField` est state-only et n'émet AUCUN SQL. Elle est donc
strictement réversible (retour à CASCADE) et ne peut perdre aucune donnée.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0002_protect_produit_donnees_reelles'),
        ('stock', '0082_fournisseur_is_archived'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prixfournisseur',
            name='fournisseur',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='prix_produits',
                to='stock.fournisseur',
            ),
        ),
    ]
