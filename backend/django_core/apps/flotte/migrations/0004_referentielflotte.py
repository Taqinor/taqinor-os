# Generated for FLOTTE6 — référentiels listes éditables du parc (additif).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("flotte", "0003_vehicule_emplacement_stock_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReferentielFlotte",
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
                    "domaine",
                    models.CharField(
                        choices=[
                            ("type_vehicule", "Type de véhicule"),
                            ("type_engin", "Type d'engin"),
                            ("energie", "Énergie"),
                            ("categorie_permis", "Catégorie de permis"),
                        ],
                        max_length=30,
                        verbose_name="Domaine",
                    ),
                ),
                ("code", models.CharField(max_length=40, verbose_name="Code")),
                (
                    "libelle",
                    models.CharField(max_length=120, verbose_name="Libellé"),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=0, verbose_name="Ordre"),
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
                        related_name="referentiels_flotte",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Référentiel de flotte",
                "verbose_name_plural": "Référentiels de flotte",
                "ordering": ["domaine", "ordre", "libelle"],
                "unique_together": {("company", "domaine", "code")},
            },
        ),
    ]
