# XSTK15 — Unites de mesure & conditionnements (touret/carton...).
# Additif : Produit.unite_stock (defaut "unite" = comportement historique
# inchange) + nouveau modele ConditionnementProduit.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0061_xstk14_revalorisation_stock"),
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="produit",
            name="unite_stock",
            field=models.CharField(
                default="unité", max_length=20,
                verbose_name="Unité de stock"),
        ),
        migrations.CreateModel(
            name="ConditionnementProduit",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("nom", models.CharField(
                    help_text="Ex. « Touret 100 m », « Carton 50 ».",
                    max_length=100)),
                ("facteur", models.DecimalField(
                    decimal_places=3, max_digits=10,
                    help_text="Combien d'unités de stock ce "
                              "conditionnement représente (ex. 100 pour un "
                              "touret de 100 m).")),
                ("code_barres", models.CharField(
                    blank=True, max_length=64, null=True,
                    help_text="Code-barres du conditionnement (optionnel, "
                              "résolution par scan).")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="conditionnements_produit",
                    to="authentication.company")),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="conditionnements", to="stock.produit")),
            ],
            options={
                "verbose_name": "Conditionnement produit",
                "verbose_name_plural": "Conditionnements produit",
                "ordering": ["produit__nom", "nom"],
            },
        ),
        migrations.AddConstraint(
            model_name="conditionnementproduit",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    models.Q(("code_barres__isnull", True), _negated=True),
                    models.Q(("code_barres", ""), _negated=True)),
                fields=("company", "code_barres"),
                name="stock_conditionnement_company_code_barres_uniq"),
        ),
    ]
