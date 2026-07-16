# NTHOT2 — Tarification saisonnière (rack/corporate/ota).
# Hand-authored (see 0001_initial.py note on the host Django version mismatch).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospitality", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanTarifaire",
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
                    "canal",
                    models.CharField(
                        choices=[
                            ("rack", "Rack (tarif public)"),
                            ("corporate", "Corporate"),
                            ("ota", "OTA"),
                        ],
                        default="rack",
                        max_length=10,
                    ),
                ),
                ("date_debut", models.DateField(verbose_name="Date de début")),
                ("date_fin", models.DateField(verbose_name="Date de fin")),
                (
                    "prix_nuit_ht",
                    models.DecimalField(
                        decimal_places=2, max_digits=10, verbose_name="Prix/nuit HT"
                    ),
                ),
                (
                    "min_nuits",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Minimum de nuits"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hospitality_plans_tarifaires",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "type_chambre",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plans_tarifaires",
                        to="hospitality.typechambre",
                        verbose_name="Type de chambre",
                    ),
                ),
            ],
            options={
                "verbose_name": "Plan tarifaire",
                "verbose_name_plural": "Plans tarifaires",
                "ordering": ["-date_debut"],
            },
        ),
    ]
