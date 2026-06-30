# Generated for FG148 — campagnes de versement des commissions (payout run).

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0019_travauxencours"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CommissionPayoutRun",
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
                    "reference",
                    models.CharField(
                        blank=True, default="", max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "periode",
                    models.CharField(
                        blank=True, default="", max_length=7,
                        verbose_name="Période (YYYY-MM)",
                    ),
                ),
                (
                    "date_run",
                    models.DateField(verbose_name="Date du run"),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("valide", "Validé"),
                            ("poste", "Posté"),
                        ],
                        default="brouillon",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "total",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Total des commissions",
                    ),
                ),
                (
                    "ecriture_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID de l'écriture OD",
                    ),
                ),
                (
                    "date_validation",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Validé le",
                    ),
                ),
                (
                    "date_poste",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Posté le",
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
                        related_name="commission_payout_runs",
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
                        related_name="commission_payout_runs_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Campagne de commissions",
                "verbose_name_plural": "Campagnes de commissions",
                "ordering": ["-date_run", "-id"],
            },
        ),
        migrations.CreateModel(
            name="CommissionPayoutLine",
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
                    "commercial_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du commercial",
                    ),
                ),
                (
                    "commercial_nom",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Commercial",
                    ),
                ),
                (
                    "base",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Base de calcul",
                    ),
                ),
                (
                    "taux",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=6,
                        verbose_name="Taux de commission (%)",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant dû",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Détail",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commission_payout_lines",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes",
                        to="compta.commissionpayoutrun",
                        verbose_name="Campagne",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne de commission",
                "verbose_name_plural": "Lignes de commission",
                "ordering": ["run", "commercial_nom", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="commissionpayoutrun",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_commrun_reference",
            ),
        ),
    ]
