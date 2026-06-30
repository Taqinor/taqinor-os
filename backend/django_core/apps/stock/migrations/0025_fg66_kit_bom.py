import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("stock", "0024_dc15_fournisseur_identite"),
    ]

    operations = [
        migrations.CreateModel(
            name="KitProduit",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=255)),
                ("sku", models.CharField(
                    blank=True, max_length=50, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("is_archived", models.BooleanField(default=False)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_mise_a_jour", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="kits_produit",
                    to="authentication.company")),
            ],
            options={
                "verbose_name": "Kit / nomenclature",
                "verbose_name_plural": "Kits / nomenclatures",
                "ordering": ["nom"],
                "unique_together": {("company", "sku")},
            },
        ),
        migrations.CreateModel(
            name="KitComposant",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("quantite", models.DecimalField(
                    decimal_places=2, default=1, max_digits=12,
                    help_text="Quantité de ce produit dans une unité de kit.")),
                ("kit", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="composants", to="stock.kitproduit")),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="composants_kit", to="stock.produit")),
            ],
            options={
                "verbose_name": "Composant de kit",
                "verbose_name_plural": "Composants de kit",
                "ordering": ["id"],
                "unique_together": {("kit", "produit")},
            },
        ),
    ]
