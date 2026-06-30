# Generated for FG152 — provisions pour créances douteuses.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0021_budget_budgetligne"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProvisionCreance",
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
                        verbose_name="Client",
                    ),
                ),
                (
                    "base",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Créance échue (base)",
                    ),
                ),
                (
                    "taux",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=5,
                        verbose_name="Taux de provision (%)",
                    ),
                ),
                (
                    "dotation",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Dotation provisionnée",
                    ),
                ),
                (
                    "anciennete_jours",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Antériorité (jours)",
                    ),
                ),
                (
                    "date_dotation",
                    models.DateField(verbose_name="Date de dotation"),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("dotation", "Dotation"),
                            ("reprise", "Reprise"),
                        ],
                        default="dotation",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "ecriture_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID de l'écriture de dotation",
                    ),
                ),
                (
                    "ecriture_reprise_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID de l'écriture de reprise",
                    ),
                ),
                (
                    "date_reprise",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de reprise",
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
                        related_name="provisions_creances",
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
                        related_name="provisions_creances_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Provision pour créance douteuse",
                "verbose_name_plural": "Provisions pour créances douteuses",
                "ordering": ["-date_dotation", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="provisioncreance",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_provcreance_ref",
            ),
        ),
    ]
