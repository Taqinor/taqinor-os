# Generated for FG149 — budgets annuels & suivi budget-vs-réalisé.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


def _mois_field():
    return models.DecimalField(
        decimal_places=2, default=Decimal("0"), max_digits=14)


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0020_commissionpayoutrun_commissionpayoutline"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Budget",
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
                ("annee", models.PositiveIntegerField(verbose_name="Année")),
                (
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("approuve", "Approuvé"),
                            ("cloture", "Clôturé"),
                        ],
                        default="brouillon",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="budgets",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="budgets_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Budget",
                "verbose_name_plural": "Budgets",
                "ordering": ["-annee", "-id"],
            },
        ),
        migrations.CreateModel(
            name="BudgetLigne",
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
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
                ("m01", _mois_field()),
                ("m02", _mois_field()),
                ("m03", _mois_field()),
                ("m04", _mois_field()),
                ("m05", _mois_field()),
                ("m06", _mois_field()),
                ("m07", _mois_field()),
                ("m08", _mois_field()),
                ("m09", _mois_field()),
                ("m10", _mois_field()),
                ("m11", _mois_field()),
                ("m12", _mois_field()),
                (
                    "budget",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes",
                        to="compta.budget",
                        verbose_name="Budget",
                    ),
                ),
                (
                    "centre_cout",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="budget_lignes",
                        to="compta.centrecout",
                        verbose_name="Centre de coût",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="budget_lignes",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "compte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_lignes",
                        to="compta.comptecomptable",
                        verbose_name="Compte",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne de budget",
                "verbose_name_plural": "Lignes de budget",
                "ordering": ["budget", "compte__numero", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="budget",
            constraint=models.UniqueConstraint(
                fields=("company", "annee", "libelle"),
                name="uniq_budget_an_lib",
            ),
        ),
    ]
