# Generated for FG139 — retenue à la source (RAS) sur honoraires/prestations.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0013_declarationtva"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RetenueSource",
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
                    "piece",
                    models.CharField(
                        blank=True, default="", max_length=80,
                        verbose_name="Pièce / facture",
                    ),
                ),
                (
                    "date_piece",
                    models.DateField(verbose_name="Date de la pièce"),
                ),
                (
                    "type_prestation",
                    models.CharField(
                        choices=[
                            ("honoraires", "Honoraires"),
                            ("redevances", "Redevances"),
                            ("loyers", "Loyers"),
                            ("prestations", "Prestations de services"),
                            ("autre", "Autre"),
                        ],
                        default="honoraires",
                        max_length=12,
                        verbose_name="Type de prestation",
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
                        verbose_name="Nom du prestataire",
                    ),
                ),
                (
                    "identifiant_fiscal",
                    models.CharField(
                        blank=True, default="", max_length=30,
                        verbose_name="Identifiant fiscal (IF/ICE)",
                    ),
                ),
                (
                    "base",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Base imposable",
                    ),
                ),
                (
                    "taux",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("10.00"),
                        max_digits=5,
                        verbose_name="Taux de RAS (%)",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant retenu",
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
                        related_name="retenues_source",
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
                        related_name="retenues_source_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Enregistrée par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Retenue à la source",
                "verbose_name_plural": "Retenues à la source",
                "ordering": ["-date_piece", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="retenuesource",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_ras_reference",
            ),
        ),
    ]
