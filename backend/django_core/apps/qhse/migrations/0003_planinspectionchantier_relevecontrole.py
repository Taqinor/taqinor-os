# Generated for QHSE4 — ITP appliqué : plan chantier + relevés de contrôle.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("qhse", "0002_planinspectionmodele_pointcontrolemodele"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanInspectionChantier",
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
                    "chantier_id",
                    models.PositiveIntegerField(verbose_name="ID du chantier"),
                ),
                (
                    "date_ouverture",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'ouverture"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_cours", "En cours"),
                            ("cloture", "Clôturé"),
                        ],
                        default="en_cours",
                        max_length=10,
                        verbose_name="Statut",
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
                        related_name="qhse_plans_chantier",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "modele",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="instances_chantier",
                        to="qhse.planinspectionmodele",
                        verbose_name="Modèle d'ITP",
                    ),
                ),
            ],
            options={
                "verbose_name": "Plan d'inspection chantier",
                "verbose_name_plural": "Plans d'inspection chantier",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="ReleveControle",
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
                    "valeur",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=500,
                        verbose_name="Valeur relevée",
                    ),
                ),
                (
                    "conforme",
                    models.BooleanField(
                        blank=True, null=True, verbose_name="Conforme"
                    ),
                ),
                (
                    "photo_key",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=500,
                        verbose_name="Clé photo",
                    ),
                ),
                (
                    "date_releve",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Date du relevé"
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
                        related_name="qhse_releves",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "plan_chantier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="releves",
                        to="qhse.planinspectionchantier",
                        verbose_name="Plan d'inspection chantier",
                    ),
                ),
                (
                    "point",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="releves",
                        to="qhse.pointcontrolemodele",
                        verbose_name="Point de contrôle (modèle)",
                    ),
                ),
                (
                    "releve_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_releves_effectues",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Relevé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Relevé de contrôle",
                "verbose_name_plural": "Relevés de contrôle",
                "ordering": ["plan_chantier", "point__ordre", "id"],
            },
        ),
    ]
