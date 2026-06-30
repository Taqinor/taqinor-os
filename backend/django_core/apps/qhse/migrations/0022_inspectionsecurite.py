# Generated for QHSE33 — Inspection sécurité planifiée (→ NCR).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("qhse", "0021_analyseincident_causeincident"),
    ]

    operations = [
        migrations.CreateModel(
            name="InspectionSecurite",
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
                        blank=True,
                        default="",
                        max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                ("titre", models.CharField(max_length=255, verbose_name="Titre")),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("planifiee", "Planifiée"),
                            ("realisee", "Réalisée"),
                            ("annulee", "Annulée"),
                        ],
                        default="planifiee",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "resultat",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("conforme", "Conforme"),
                            ("non_conforme", "Non conforme"),
                        ],
                        default="en_attente",
                        max_length=15,
                        verbose_name="Résultat",
                    ),
                ),
                (
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du chantier"
                    ),
                ),
                (
                    "date_prevue",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date prévue"
                    ),
                ),
                (
                    "date_realisee",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date réalisée"
                    ),
                ),
                (
                    "observations",
                    models.TextField(
                        blank=True, default="", verbose_name="Observations"
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
                        related_name="qhse_inspections_securite",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "inspecteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_inspections_securite",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Inspecteur",
                    ),
                ),
                (
                    "ncr",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="inspections_securite",
                        to="qhse.nonconformite",
                        verbose_name="Non-conformité levée",
                    ),
                ),
            ],
            options={
                "verbose_name": "Inspection sécurité",
                "verbose_name_plural": "Inspections sécurité",
                "ordering": ["-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="inspectionsecurite",
            constraint=models.UniqueConstraint(
                fields=("company", "reference"),
                name="qhse_inspsec_co_ref_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="inspectionsecurite",
            index=models.Index(
                fields=["company", "statut"], name="qhse_inspsec_co_statut"
            ),
        ),
        migrations.AddIndex(
            model_name="inspectionsecurite",
            index=models.Index(
                fields=["company", "date_prevue"], name="qhse_inspsec_co_prevue"
            ),
        ),
        migrations.AddIndex(
            model_name="inspectionsecurite",
            index=models.Index(
                fields=["company", "chantier_id"], name="qhse_inspsec_co_chant"
            ),
        ),
    ]
