# Generated for QHSE40 — IndicateurESG + export reporting.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0026_bilancarbone_lignebilancarbone"),
    ]

    operations = [
        migrations.CreateModel(
            name="IndicateurESG",
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
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Code",
                    ),
                ),
                ("libelle", models.CharField(max_length=255, verbose_name="Libellé")),
                (
                    "pilier",
                    models.CharField(
                        choices=[
                            ("environnement", "Environnement"),
                            ("social", "Social"),
                            ("gouvernance", "Gouvernance"),
                        ],
                        default="environnement",
                        max_length=15,
                        verbose_name="Pilier ESG",
                    ),
                ),
                (
                    "valeur",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=18,
                        null=True,
                        verbose_name="Valeur",
                    ),
                ),
                (
                    "cible",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=18,
                        null=True,
                        verbose_name="Cible",
                    ),
                ),
                (
                    "unite",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Unité",
                    ),
                ),
                (
                    "annee",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Année"
                    ),
                ),
                (
                    "periode",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Période",
                    ),
                ),
                (
                    "tendance_souhaitee",
                    models.CharField(
                        choices=[
                            ("hausse_favorable", "Hausse favorable"),
                            ("baisse_favorable", "Baisse favorable"),
                            ("neutre", "Neutre"),
                        ],
                        default="neutre",
                        max_length=20,
                        verbose_name="Tendance souhaitée",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True, default="", verbose_name="Notes"
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
                        related_name="qhse_indicateurs_esg",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "bilan_carbone",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="indicateurs_esg",
                        to="qhse.bilancarbone",
                        verbose_name="Bilan carbone lié",
                    ),
                ),
            ],
            options={
                "verbose_name": "Indicateur ESG",
                "verbose_name_plural": "Indicateurs ESG",
                "ordering": ["pilier", "code", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="indicateuresg",
            index=models.Index(
                fields=["company", "pilier"], name="qhse_esg_co_pilier"
            ),
        ),
        migrations.AddIndex(
            model_name="indicateuresg",
            index=models.Index(
                fields=["company", "annee"], name="qhse_esg_co_annee"
            ),
        ),
    ]
