# Generated for FG144 — droit de timbre sur encaissements en espèces.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0014_retenuesource"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TimbreFiscal",
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
                    "date_encaissement",
                    models.DateField(verbose_name="Date d'encaissement"),
                ),
                (
                    "paiement_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du paiement d'origine",
                    ),
                ),
                (
                    "facture_ref",
                    models.CharField(
                        blank=True, default="", max_length=80,
                        verbose_name="Facture / pièce",
                    ),
                ),
                (
                    "mode_reglement",
                    models.CharField(
                        blank=True, default="especes", max_length=20,
                        verbose_name="Mode de règlement",
                    ),
                ),
                (
                    "tiers_type",
                    models.CharField(
                        blank=True, default="", max_length=20,
                        verbose_name="Type de tiers",
                    ),
                ),
                (
                    "tiers_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du tiers",
                    ),
                ),
                (
                    "tiers_nom",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Nom du payeur",
                    ),
                ),
                (
                    "base",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant encaissé (base)",
                    ),
                ),
                (
                    "taux",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.25"),
                        max_digits=5,
                        verbose_name="Taux du droit de timbre (%)",
                    ),
                ),
                (
                    "minimum",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.25"),
                        max_digits=8,
                        verbose_name="Minimum de perception",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Droit de timbre",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_verser", "À verser"),
                            ("versee", "Versée"),
                        ],
                        default="a_verser",
                        max_length=10,
                        verbose_name="Statut",
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
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="timbres_fiscaux",
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
                        related_name="timbres_fiscaux_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Enregistré par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Droit de timbre",
                "verbose_name_plural": "Droits de timbre",
                "ordering": ["-date_encaissement", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="timbrefiscal",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_timbre_reference",
            ),
        ),
        migrations.AddConstraint(
            model_name="timbrefiscal",
            constraint=models.UniqueConstraint(
                condition=models.Q(("paiement_id__isnull", False)),
                fields=("company", "paiement_id"),
                name="uniq_timbre_paiement",
            ),
        ),
    ]
