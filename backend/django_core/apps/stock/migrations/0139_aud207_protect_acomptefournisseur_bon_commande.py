"""AUD207 — `AcompteFournisseur.bon_commande` : CASCADE -> PROTECT.

Même patron que `achats/0003_protect_fournisseur_prix` et
`achats/0004_aud207_protect_paiementfournisseur_facture` (côté paiement) :
un acompte fournisseur réellement versé n'est plus effacé silencieusement à
la suppression du BCF qui le porte
(`BonCommandeFournisseurViewSet.perform_destroy` refuse déjà en 400
explicite AVANT ce point — cette contrainte DB est le filet de sécurité pour
tout autre chemin de suppression, y compris l'admin Django).

`on_delete` est un attribut NON-DB (`django.db.models.Field.non_db_attrs`) :
cette `AlterField` est state-only et n'émet AUCUN SQL. Elle est donc
strictement réversible (retour à CASCADE) et ne peut perdre aucune donnée.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0138_aud214_rdv_quai_exclusion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='acomptefournisseur',
            name='bon_commande',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='acomptes',
                to='achats.boncommandefournisseur',
            ),
        ),
    ]
