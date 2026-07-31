"""NTPRT25 — `Fournisseur.statut_validation` (auto-inscription portail).

ADDITIF et RÉVERSIBLE : une colonne texte avec `default='valide'`, donc tous
les fournisseurs existants restent VALIDÉS et strictement visibles comme
avant. Champ délibérément SÉPARÉ de `Fournisseur.statut` (blocage commercial
XPUR4) : y ajouter une valeur « en attente » aurait fait passer un candidat non
validé à travers les gardes de création BCF/paiement, qui ne testent que
`bloque_commandes`/`bloque_total`.

`git revert` suffit : `RemoveField` ne perd que l'information de validation
(aucune donnée métier).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0082_fournisseur_is_archived'),
    ]

    operations = [
        migrations.AddField(
            model_name='fournisseur',
            name='statut_validation',
            field=models.CharField(
                choices=[
                    ('valide', 'Validé'),
                    ('en_attente_validation', 'En attente de validation'),
                    ('rejete', 'Rejeté'),
                ],
                default='valide',
                help_text="Validation d'une candidature d'auto-inscription au "
                          "portail fournisseur. « En attente » = invisible des "
                          "listes de sourcing automatique tant qu'un admin "
                          "interne n'a pas tranché.",
                max_length=24,
            ),
        ),
    ]
