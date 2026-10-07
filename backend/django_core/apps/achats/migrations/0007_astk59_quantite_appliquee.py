"""ASTK59 — `LigneReceptionFournisseur.quantite_appliquee` : quantité
RÉELLEMENT entrée en stock à la confirmation (après plafonnement au reste dû).

Additive et revertable : nullable, aucune donnée réécrite. Une ligne
historique (NULL) se relit sur `quantite` (repli du helper
`apps.stock.services.quantite_entree_ligne_reception`).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0006_astk106_imputation_acompte_fournisseur'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignereceptionfournisseur',
            name='quantite_appliquee',
            field=models.IntegerField(
                blank=True, null=True,
                help_text='ASTK59 — quantité réellement entrée en stock à la '
                          'confirmation (plafonnée au reste dû). NULL = '
                          'ligne antérieure : repli sur `quantite`.'),
        ),
    ]
