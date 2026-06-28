# Generated for FG131 — Rapprochement 3 voies (BC ↔ réception ↔ facture).

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("compta", "0008_bordereauremise_effet_ligneprevisionneltresorerie_and_more"),
        ("stock", "0023_fg54_fg61_fg62_fg63_fg64_stock_features"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Rapprochement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("ecart", "Écart détecté"),
                            ("concordant", "Concordant"),
                            ("valide", "Validé (bon à payer)"),
                        ],
                        default="en_attente",
                        max_length=12,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "tolerance",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Tolérance",
                    ),
                ),
                (
                    "montant_commande",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant commandé (HT)",
                    ),
                ),
                (
                    "montant_recu",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant reçu (HT)",
                    ),
                ),
                (
                    "montant_facture",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant facturé (HT)",
                    ),
                ),
                (
                    "ecart",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Écart (facturé − reçu)",
                    ),
                ),
                (
                    "note",
                    models.TextField(blank=True, null=True, verbose_name="Note"),
                ),
                (
                    "date_evaluation",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Dernière évaluation"
                    ),
                ),
                (
                    "date_validation",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Validé le"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compta_rapprochements",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "bon_commande",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compta_rapprochements",
                        to="stock.boncommandefournisseur",
                        verbose_name="Bon de commande fournisseur",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="compta_rapprochements_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
                (
                    "valide_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="compta_rapprochements_valides",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Validé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Rapprochement 3 voies",
                "verbose_name_plural": "Rapprochements 3 voies",
                "ordering": ["-date_creation", "-id"],
                "unique_together": {("company", "bon_commande")},
            },
        ),
    ]
