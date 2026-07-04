# XPUR16 — Lignes libres / services sur le BCF (achats hors stock).
# `LigneBonCommandeFournisseur.produit` devient nullable (+ `designation`
# libre, `sans_stock`) : une ligne « Transport Casablanca » compte dans le
# total/l'approbation/la facturation mais ne génère jamais de MouvementStock
# à la réception. `LigneReceptionFournisseur.produit` devient nullable en
# miroir (dérivé de `ligne_commande.produit`). Additif : une ligne catalogue
# existante (produit renseigné, sans_stock=False) garde son comportement.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0046_xpur14_prix_fournisseur_enrichi"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lignebondecommandefournisseur",
            name="produit",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lignes_bon_commande_fournisseur",
                to="stock.produit"),
        ),
        migrations.AddField(
            model_name="lignebondecommandefournisseur",
            name="designation",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="lignebondecommandefournisseur",
            name="sans_stock",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="lignereceptionfournisseur",
            name="produit",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lignes_reception_fournisseur",
                to="stock.produit"),
        ),
    ]
