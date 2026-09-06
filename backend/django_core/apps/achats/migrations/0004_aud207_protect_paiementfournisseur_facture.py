"""AUD207 — `PaiementFournisseur.facture` : CASCADE -> PROTECT.

Même patron que `0003_protect_fournisseur_prix` : un paiement fournisseur
réellement versé n'est plus effacé silencieusement à la suppression de la
facture qui le porte (`FactureFournisseurViewSet.perform_destroy` refuse
déjà en 400 explicite AVANT ce point — cette contrainte DB est le filet de
sécurité pour tout autre chemin de suppression, y compris l'admin Django).

`on_delete` est un attribut NON-DB (`django.db.models.Field.non_db_attrs`) :
cette `AlterField` est state-only et n'émet AUCUN SQL. Elle est donc
strictement réversible (retour à CASCADE) et ne peut perdre aucune donnée.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0003_protect_fournisseur_prix'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paiementfournisseur',
            name='facture',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='paiements',
                to='achats.facturefournisseur',
            ),
        ),
    ]
