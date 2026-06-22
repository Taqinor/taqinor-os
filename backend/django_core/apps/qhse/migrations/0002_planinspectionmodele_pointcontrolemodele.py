# Generated for QHSE2 — ITP (Inspection & Test Plan) models.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("qhse", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanInspectionModele",
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
                    "code",
                    models.CharField(
                        blank=True, default="", max_length=50, verbose_name="Code"
                    ),
                ),
                ("nom", models.CharField(max_length=255, verbose_name="Nom")),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
                    ),
                ),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_plans_inspection",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Modèle de plan d'inspection",
                "verbose_name_plural": "Modèles de plan d'inspection",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="PointControleModele",
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
                ("ordre", models.PositiveIntegerField(default=0, verbose_name="Ordre")),
                (
                    "intitule",
                    models.CharField(max_length=255, verbose_name="Intitulé"),
                ),
                (
                    "phase",
                    models.CharField(
                        blank=True, default="", max_length=120, verbose_name="Phase"
                    ),
                ),
                (
                    "type_releve",
                    models.CharField(
                        choices=[
                            ("mesure", "Mesure"),
                            ("visuel", "Visuel"),
                            ("document", "Document"),
                            ("essai", "Essai"),
                        ],
                        default="visuel",
                        max_length=10,
                        verbose_name="Type de relevé",
                    ),
                ),
                (
                    "hold_point",
                    models.BooleanField(
                        default=False, verbose_name="Point d'arrêt"
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
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
                        related_name="qhse_points_controle",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="points",
                        to="qhse.planinspectionmodele",
                        verbose_name="Plan d'inspection",
                    ),
                ),
            ],
            options={
                "verbose_name": "Point de contrôle (modèle)",
                "verbose_name_plural": "Points de contrôle (modèle)",
                "ordering": ["plan", "ordre", "id"],
            },
        ),
    ]
