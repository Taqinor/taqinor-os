# Hand-authored (NTPRO2) — see 0001_initial.py header for why manage.py
# makemigrations cannot run in this host env (Django 6.0.6 vs pinned 5.1.4).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("immobilier", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Locataire",
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
                    "type_locataire",
                    models.CharField(
                        choices=[
                            ("particulier", "Particulier"),
                            ("societe", "Société"),
                        ],
                        default="particulier",
                        max_length=12,
                        verbose_name="Type",
                    ),
                ),
                (
                    "nom",
                    models.CharField(
                        max_length=255, verbose_name="Nom / raison sociale"
                    ),
                ),
                (
                    "cin",
                    models.CharField(
                        blank=True, default="", max_length=30, verbose_name="CIN"
                    ),
                ),
                (
                    "ice",
                    models.CharField(
                        blank=True, default="", max_length=30, verbose_name="ICE"
                    ),
                ),
                (
                    "telephone",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Téléphone",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, default="", max_length=254, verbose_name="Email"
                    ),
                ),
                (
                    "adresse",
                    models.TextField(blank=True, default="", verbose_name="Adresse"),
                ),
                (
                    "client_ventes_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID client ventes (crm.Client)",
                    ),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_locataires",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Locataire",
                "verbose_name_plural": "Locataires",
                "ordering": ["nom"],
            },
        ),
    ]
