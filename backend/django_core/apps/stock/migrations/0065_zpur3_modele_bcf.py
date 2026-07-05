# ZPUR3 — Modèle de bon de commande fournisseur réutilisable (purchase
# template) : nom + fournisseur optionnel + lignes produit/quantité par
# défaut. Nouvelle table, additif — aucun impact sur les BCF existants.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
        ("stock", "0064_zpur1_politique_facturation_achat"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModeleBonCommandeFournisseur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("nom", models.CharField(max_length=150)),
                ("note", models.TextField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_mise_a_jour", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="modeles_bcf", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="modeles_bcf_crees",
                    to=settings.AUTH_USER_MODEL)),
                ("fournisseur", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="modeles_bcf", to="stock.fournisseur")),
            ],
            options={
                "verbose_name": "Modèle de bon de commande fournisseur",
                "verbose_name_plural": (
                    "Modèles de bon de commande fournisseur"),
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="ModeleBonCommandeFournisseurLigne",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("quantite", models.PositiveIntegerField(default=1)),
                ("modele", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lignes",
                    to="stock.modeleboncommandefournisseur")),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lignes_modele_bcf", to="stock.produit")),
            ],
            options={
                "verbose_name": "Ligne de modèle de BCF",
                "verbose_name_plural": "Lignes de modèle de BCF",
                "ordering": ["id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="modeleboncommandefournisseurligne",
            unique_together={("modele", "produit")},
        ),
    ]
