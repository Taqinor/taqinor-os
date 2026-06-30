# Generated for QHSE39 — BilanCarbone + LigneBilanCarbone (scopes 1/2/3).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0025_conformiteenvironnementale"),
    ]

    operations = [
        migrations.CreateModel(
            name="BilanCarbone",
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
                ("libelle", models.CharField(max_length=255, verbose_name="Libellé")),
                ("annee", models.PositiveIntegerField(verbose_name="Année")),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("valide", "Validé"),
                            ("archive", "Archivé"),
                        ],
                        default="brouillon",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "perimetre",
                    models.TextField(
                        blank=True, default="", verbose_name="Périmètre"
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
                        related_name="qhse_bilans_carbone",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Bilan carbone",
                "verbose_name_plural": "Bilans carbone",
                "ordering": ["-annee", "-id"],
            },
        ),
        migrations.CreateModel(
            name="LigneBilanCarbone",
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
                ("libelle", models.CharField(max_length=255, verbose_name="Libellé")),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("scope_1", "Scope 1 — émissions directes"),
                            ("scope_2", "Scope 2 — énergie achetée"),
                            ("scope_3", "Scope 3 — autres indirectes"),
                        ],
                        default="scope_1",
                        max_length=10,
                        verbose_name="Scope",
                    ),
                ),
                (
                    "categorie",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="Catégorie",
                    ),
                ),
                (
                    "quantite",
                    models.DecimalField(
                        decimal_places=3,
                        default=0,
                        max_digits=14,
                        verbose_name="Quantité d'activité",
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
                    "facteur_emission",
                    models.DecimalField(
                        decimal_places=6,
                        default=0,
                        max_digits=14,
                        verbose_name="Facteur d'émission (tCO₂e/unité)",
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
                        related_name="qhse_lignes_bilan_carbone",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "bilan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes",
                        to="qhse.bilancarbone",
                        verbose_name="Bilan",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne de bilan carbone",
                "verbose_name_plural": "Lignes de bilan carbone",
                "ordering": ["scope", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="bilancarbone",
            constraint=models.UniqueConstraint(
                fields=("company", "annee", "libelle"),
                name="qhse_bilan_co_an_lib_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="bilancarbone",
            index=models.Index(
                fields=["company", "annee"], name="qhse_bilan_co_annee"
            ),
        ),
        migrations.AddIndex(
            model_name="lignebilancarbone",
            index=models.Index(
                fields=["bilan", "scope"], name="qhse_lbilan_bilan_scope"
            ),
        ),
    ]
