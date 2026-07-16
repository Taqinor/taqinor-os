# Hand-authored (NTPRO4) — see 0001_initial.py header for why manage.py
# makemigrations cannot run in this host env (Django 6.0.6 vs pinned 5.1.4).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("immobilier", "0003_bail"),
    ]

    operations = [
        migrations.CreateModel(
            name="RevisionLoyer",
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
                ("date_effet", models.DateField(verbose_name="Date d'effet")),
                (
                    "ancien_loyer",
                    models.DecimalField(
                        decimal_places=2, max_digits=10, verbose_name="Ancien loyer"
                    ),
                ),
                (
                    "nouveau_loyer",
                    models.DecimalField(
                        decimal_places=2, max_digits=10, verbose_name="Nouveau loyer"
                    ),
                ),
                (
                    "indice",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="Indice de référence",
                    ),
                ),
                (
                    "taux_variation",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=6,
                        null=True,
                        verbose_name="Taux de variation (%)",
                    ),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "bail",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisions",
                        to="immobilier.bail",
                        verbose_name="Bail",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_revisions_loyer",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Révision de loyer",
                "verbose_name_plural": "Révisions de loyer",
                "ordering": ["-date_effet", "-id"],
            },
        ),
    ]
