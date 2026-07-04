# Generated for XPLT6 — configurable threshold alerts on aggregated KPIs.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("reporting", "0003_fg96_dashboard_config"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KpiAlerte",
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
                ("nom", models.CharField(blank=True, default="", max_length=120)),
                (
                    "kpi",
                    models.CharField(
                        choices=[
                            ("dso", "DSO (délai moyen de recouvrement, jours)"),
                            (
                                "encours_echu_total",
                                "Encours client échu total (MAD)",
                            ),
                            (
                                "valeur_stock_totale",
                                "Valeur de stock totale (MAD)",
                            ),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "operateur",
                    models.CharField(
                        choices=[
                            ("sup", ">"),
                            ("sup_egal", ">="),
                            ("inf", "<"),
                            ("inf_egal", "<="),
                        ],
                        default="sup",
                        max_length=10,
                    ),
                ),
                ("seuil", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "destinataire_role",
                    models.CharField(blank=True, default="", max_length=20),
                ),
                ("actif", models.BooleanField(default=True)),
                ("deja_notifie", models.BooleanField(default=False)),
                (
                    "derniere_valeur",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=14, null=True
                    ),
                ),
                (
                    "derniere_evaluation_le",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reporting_kpi_alertes",
                        to="authentication.company",
                    ),
                ),
                (
                    "destinataires_utilisateurs",
                    models.ManyToManyField(
                        blank=True,
                        related_name="reporting_kpi_alertes_destinataire",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Alerte KPI",
                "verbose_name_plural": "Alertes KPI",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
