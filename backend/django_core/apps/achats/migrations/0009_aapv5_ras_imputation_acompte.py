"""AAPV5 (D-AAPV-2) — ``montant_ras_tva`` sur ImputationAcompteFournisseur : la RAS-TVA
restante portée par l'imputation qui solde une facture fournisseur.
Additive (défaut 0), revertable (retrait de la colonne)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0008_err_astk54_facture_reception'),
    ]

    operations = [
        migrations.AddField(
            model_name='imputationacomptefournisseur',
            name='montant_ras_tva',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]
