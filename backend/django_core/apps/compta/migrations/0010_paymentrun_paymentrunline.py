# Generated for FG133/FG134 — campagnes de règlement fournisseurs (payment run)
# + génération du fichier de virement bancaire.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("compta", "0009_rapprochement"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentRun",
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
                        blank=True, default="", max_length=80,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "mode_paiement",
                    models.CharField(
                        choices=[
                            ("virement", "Virement bancaire"),
                            ("cheque", "Chèque"),
                            ("especes", "Espèces"),
                        ],
                        default="virement",
                        max_length=10,
                        verbose_name="Mode de paiement",
                    ),
                ),
                (
                    "date_paiement",
                    models.DateField(verbose_name="Date de paiement"),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("proposee", "Proposition figée"),
                            ("postee", "Postée au grand livre"),
                        ],
                        default="brouillon",
                        max_length=12,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "total",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Total proposé",
                    ),
                ),
                (
                    "posted",
                    models.BooleanField(
                        default=False, verbose_name="Postée au grand livre"
                    ),
                ),
                (
                    "note",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Note",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créée le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compta_payment_runs",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "compte_tresorerie",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="compta_payment_runs",
                        to="compta.comptetresorerie",
                        verbose_name="Compte de trésorerie (payeur)",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="compta_payment_runs_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créée par",
                    ),
                ),
                (
                    "ecriture",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="compta_payment_runs",
                        to="compta.ecriturecomptable",
                        verbose_name="Écriture comptable",
                    ),
                ),
            ],
            options={
                "verbose_name": "Campagne de règlement fournisseurs",
                "verbose_name_plural": "Campagnes de règlement fournisseurs",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.CreateModel(
            name="PaymentRunLine",
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
                    "tiers_type",
                    models.CharField(
                        blank=True,
                        default="fournisseur",
                        max_length=20,
                        verbose_name="Type de tiers",
                    ),
                ),
                (
                    "tiers_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du tiers"
                    ),
                ),
                (
                    "beneficiaire",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Bénéficiaire",
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True, default="", max_length=80,
                        verbose_name="Référence (facture / échéance)",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant à régler",
                    ),
                ),
                (
                    "date_echeance",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'échéance"
                    ),
                ),
                (
                    "rib",
                    models.CharField(
                        blank=True, default="", max_length=40,
                        verbose_name="RIB",
                    ),
                ),
                (
                    "iban",
                    models.CharField(
                        blank=True, default="", max_length=40,
                        verbose_name="IBAN",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="compta_payment_run_lines",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "payment_run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes",
                        to="compta.paymentrun",
                        verbose_name="Campagne de règlement",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne de règlement fournisseur",
                "verbose_name_plural": "Lignes de règlement fournisseur",
                "ordering": ["date_echeance", "id"],
            },
        ),
    ]
