# Generated for FG153 — inter-sociétés / consolidation multi-entités.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0022_provisioncreance"),
    ]

    operations = [
        migrations.CreateModel(
            name="EntiteConsolidation",
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
                (
                    "pourcentage_interet",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("100.00"),
                        max_digits=5,
                        verbose_name="Pourcentage d'intérêt (%)",
                    ),
                ),
                (
                    "methode",
                    models.CharField(
                        choices=[
                            ("globale", "Intégration globale"),
                            ("equivalence", "Mise en équivalence"),
                        ],
                        default="globale",
                        max_length=12,
                        verbose_name="Méthode de consolidation",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
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
                        related_name="consolidation_perimetre",
                        to="authentication.company",
                        verbose_name="Société tête de groupe",
                    ),
                ),
                (
                    "entite",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consolidation_membre_de",
                        to="authentication.company",
                        verbose_name="Entité consolidée",
                    ),
                ),
            ],
            options={
                "verbose_name": "Entité de consolidation",
                "verbose_name_plural": "Entités de consolidation",
                "ordering": ["company", "entite"],
            },
        ),
        migrations.AddConstraint(
            model_name="entiteconsolidation",
            constraint=models.UniqueConstraint(
                fields=("company", "entite"),
                name="uniq_consol_entite",
            ),
        ),
    ]
