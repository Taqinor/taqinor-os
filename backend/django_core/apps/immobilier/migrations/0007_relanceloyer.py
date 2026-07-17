# Hand-authored (NTPRO8) — see 0001_initial.py header for why manage.py
# makemigrations cannot run in this host env (Django 6.0.6 vs pinned 5.1.4).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("immobilier", "0006_echeanceloyer"),
    ]

    operations = [
        migrations.CreateModel(
            name="RelanceLoyer",
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
                    "niveau",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Niveau 1"),
                            (2, "Niveau 2"),
                            (3, "Niveau 3"),
                        ],
                        default=1,
                        verbose_name="Niveau",
                    ),
                ),
                (
                    "date_envoi",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Date d'envoi"
                    ),
                ),
                (
                    "canal",
                    models.CharField(
                        choices=[
                            ("whatsapp", "WhatsApp"),
                            ("email", "Email"),
                            ("courrier", "Courrier"),
                        ],
                        default="whatsapp",
                        max_length=10,
                        verbose_name="Canal",
                    ),
                ),
                (
                    "template_utilise",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Template utilisé",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="immobilier_relances_loyer",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "echeance_loyer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="relances",
                        to="immobilier.echeanceloyer",
                        verbose_name="Échéance de loyer",
                    ),
                ),
            ],
            options={
                "verbose_name": "Relance loyer",
                "verbose_name_plural": "Relances loyer",
                "ordering": ["-date_envoi", "-id"],
            },
        ),
    ]
