# Hand-authored (NTPRO1) — mirrors apps/qhse/migrations/0001_initial.py style.
# The host Python env here runs Django 6.0.6 while this repo pins Django==5.1.4
# (requirements.txt), so `manage.py makemigrations` cannot run locally (fails
# on unrelated pre-existing models, e.g. CheckConstraint(check=...) removed in
# Django 6). Hand-authored to match the exact shape `makemigrations` would
# have produced from apps/immobilier/models.py.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
    ]

    operations = [
        migrations.CreateModel(
            name="Site",
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
                ("nom", models.CharField(max_length=255, verbose_name="Nom")),
                (
                    "adresse",
                    models.TextField(blank=True, default="", verbose_name="Adresse"),
                ),
                (
                    "ville",
                    models.CharField(
                        blank=True, default="", max_length=120, verbose_name="Ville"
                    ),
                ),
                (
                    "gps_lat",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Latitude GPS",
                    ),
                ),
                (
                    "gps_lng",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Longitude GPS",
                    ),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_sites",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Site",
                "verbose_name_plural": "Sites",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="Batiment",
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
                ("nom", models.CharField(max_length=255, verbose_name="Nom")),
                (
                    "nb_niveaux",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Nombre de niveaux"
                    ),
                ),
                (
                    "annee_construction",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="Année de construction",
                    ),
                ),
                (
                    "plan_ged_document_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID document GED (plan)",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_batiments",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="batiments",
                        to="immobilier.site",
                        verbose_name="Site",
                    ),
                ),
            ],
            options={
                "verbose_name": "Bâtiment",
                "verbose_name_plural": "Bâtiments",
                "ordering": ["site__nom", "nom"],
            },
        ),
        migrations.CreateModel(
            name="Niveau",
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
                    "numero",
                    models.CharField(
                        max_length=50, verbose_name="Numéro / libellé"
                    ),
                ),
                (
                    "ordre",
                    models.IntegerField(
                        default=0, verbose_name="Ordre d'affichage"
                    ),
                ),
                (
                    "batiment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="niveaux",
                        to="immobilier.batiment",
                        verbose_name="Bâtiment",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_niveaux",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Niveau",
                "verbose_name_plural": "Niveaux",
                "ordering": ["batiment_id", "ordre", "numero"],
            },
        ),
        migrations.CreateModel(
            name="Local",
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
                    models.CharField(max_length=50, verbose_name="Référence"),
                ),
                (
                    "type_local",
                    models.CharField(
                        choices=[
                            ("habitation", "Habitation"),
                            ("commerce", "Commerce"),
                            ("bureau", "Bureau"),
                            ("parking", "Parking"),
                            ("entrepot", "Entrepôt"),
                        ],
                        default="habitation",
                        max_length=15,
                        verbose_name="Type",
                    ),
                ),
                (
                    "surface_m2",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=8,
                        null=True,
                        verbose_name="Surface (m²)",
                    ),
                ),
                (
                    "tantiemes",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=8,
                        null=True,
                        verbose_name="Tantièmes",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("libre", "Libre"),
                            ("loue", "Loué"),
                            ("en_travaux", "En travaux"),
                        ],
                        default="libre",
                        max_length=12,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_locaux",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "niveau",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="locaux",
                        to="immobilier.niveau",
                        verbose_name="Niveau",
                    ),
                ),
            ],
            options={
                "verbose_name": "Local",
                "verbose_name_plural": "Locaux",
                "ordering": ["niveau_id", "reference"],
            },
        ),
    ]
