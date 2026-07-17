# NTHOT1 — App hospitality + plan des chambres/unités.
# Hand-authored (host env pins Django 6.0.6 while the repo targets 5.1.4 —
# `manage.py makemigrations` fails on an unrelated CheckConstraint API change
# in apps/stock/models.py before it ever reaches this app). Mirrors the
# structure of apps/qhse/migrations/0001_initial.py.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
    ]

    operations = [
        migrations.CreateModel(
            name="TypeChambre",
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
                ("libelle", models.CharField(max_length=100, verbose_name="Libellé")),
                (
                    "capacite_max",
                    models.PositiveIntegerField(
                        default=2, verbose_name="Capacité maximale"
                    ),
                ),
                ("description", models.TextField(blank=True, default="")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hospitality_types_chambre",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Type de chambre",
                "verbose_name_plural": "Types de chambre",
                "ordering": ["libelle"],
            },
        ),
        migrations.CreateModel(
            name="Chambre",
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
                ("numero", models.CharField(max_length=20, verbose_name="Numéro")),
                ("nom", models.CharField(blank=True, default="", max_length=100)),
                ("etage", models.CharField(blank=True, default="", max_length=20)),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("libre", "Libre"),
                            ("occupee", "Occupée"),
                            ("sale", "Sale"),
                            ("en_nettoyage", "En nettoyage"),
                            ("hors_service", "Hors service"),
                        ],
                        default="libre",
                        max_length=15,
                    ),
                ),
                (
                    "vue",
                    models.CharField(
                        blank=True, default="", max_length=100, verbose_name="Vue"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hospitality_chambres",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "type_chambre",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="chambres",
                        to="hospitality.typechambre",
                        verbose_name="Type de chambre",
                    ),
                ),
            ],
            options={
                "verbose_name": "Chambre",
                "verbose_name_plural": "Chambres",
                "ordering": ["numero"],
            },
        ),
        migrations.AddConstraint(
            model_name="chambre",
            constraint=models.UniqueConstraint(
                fields=["company", "numero"],
                name="hospitality_chambre_unique_numero_par_societe",
            ),
        ),
    ]
