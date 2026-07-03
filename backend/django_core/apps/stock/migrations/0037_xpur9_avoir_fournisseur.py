# XPUR9 — Avoir fournisseur (note de crédit AP). Additif : AvoirFournisseur
# (brouillon/valide/impute, référence AVF) + ImputationAvoirFournisseur
# (répartition sur 1..N FactureFournisseur).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0036_xpur8_acompte_fournisseur"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AvoirFournisseur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("reference", models.CharField(max_length=50)),
                ("montant_ht", models.DecimalField(
                    decimal_places=2, default=0, max_digits=14)),
                ("montant_tva", models.DecimalField(
                    decimal_places=2, default=0, max_digits=14)),
                ("montant_ttc", models.DecimalField(
                    decimal_places=2, default=0, max_digits=14)),
                ("statut", models.CharField(
                    choices=[
                        ("brouillon", "Brouillon"),
                        ("valide", "Validé"),
                        ("impute", "Imputé"),
                    ],
                    default="brouillon", max_length=20)),
                ("montant_impute", models.DecimalField(
                    decimal_places=2, default=0, max_digits=14)),
                ("note", models.TextField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_mise_a_jour", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="avoirs_fournisseur",
                    to="authentication.company")),
                ("fournisseur", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="avoirs", to="stock.fournisseur")),
                ("facture_origine", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="avoirs_origine",
                    to="stock.facturefournisseur")),
                ("retour", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="avoirs", to="stock.retourfournisseur")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="avoirs_fournisseur",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Avoir fournisseur",
                "verbose_name_plural": "Avoirs fournisseur",
                "ordering": ["-date_creation"],
                "unique_together": {("company", "reference")},
            },
        ),
        migrations.CreateModel(
            name="ImputationAvoirFournisseur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("montant", models.DecimalField(
                    decimal_places=2, max_digits=14)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="imputations_avoir_fournisseur",
                    to="authentication.company")),
                ("avoir", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="imputations", to="stock.avoirfournisseur")),
                ("facture", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="avoirs_imputes",
                    to="stock.facturefournisseur")),
            ],
            options={
                "verbose_name": "Imputation d'avoir fournisseur",
                "verbose_name_plural": "Imputations d'avoir fournisseur",
                "ordering": ["-date_creation"],
            },
        ),
    ]
