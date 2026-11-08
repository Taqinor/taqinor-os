"""AAPV5 (D-AAPV-2) — ``montant_ras_tva`` sur ImputationAvoirFournisseur : la RAS-TVA
restante portée par l'imputation qui solde une facture fournisseur.
Additive (défaut 0), revertable (retrait de la colonne)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0178_astk256_declaration_consommation_facture'),
    ]

    operations = [
        migrations.AddField(
            model_name='imputationavoirfournisseur',
            name='montant_ras_tva',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]
