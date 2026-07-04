# XPUR17 — TVA par ligne sur la facture fournisseur (taux marocains). Miroir
# de ventes.LigneFacture.taux_tva : NULL = ligne historique -> le taux global
# de la facture continue de s'appliquer (comportement inchangé). Une ligne
# NOUVELLE sans taux explicite prend 20 % par défaut.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0047_xpur16_lignes_libres_bcf"),
    ]

    operations = [
        migrations.AddField(
            model_name="lignefacturefournisseur",
            name="taux_tva",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=20, max_digits=5,
                null=True),
        ),
    ]
