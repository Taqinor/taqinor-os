# NTSEC14 — appareils de confiance (« se souvenir de cet appareil N jours »).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TrustedDevice",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "device_fingerprint",
                    models.CharField(
                        db_index=True,
                        max_length=128,
                        verbose_name="Empreinte appareil",
                    ),
                ),
                ("approuve_le", models.DateTimeField(verbose_name="Approuvé le")),
                ("expire_le", models.DateTimeField(verbose_name="Expire le")),
                (
                    "revoque_le",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Révoqué le"
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        verbose_name="Appareil",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trusted_devices",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur",
                    ),
                ),
                (
                    "approuve_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Approuvé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Appareil de confiance",
                "verbose_name_plural": "Appareils de confiance",
                "ordering": ("-approuve_le",),
            },
        ),
    ]
