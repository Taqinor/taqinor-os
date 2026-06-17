# N98 — programme de parrainage (parrain Client → filleul lead/client). Additif.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("crm", "0016_client_custom_data_lead_custom_data"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Parrainage",
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
                    "filleul_nom",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("converti", "Converti"),
                            ("recompense_versee", "Récompense versée"),
                        ],
                        default="en_attente",
                        max_length=20,
                    ),
                ),
                (
                    "recompense",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=10, null=True
                    ),
                ),
                ("notes", models.TextField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parrainages",
                        to="authentication.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "filleul_client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="parrainages_recus",
                        to="crm.client",
                    ),
                ),
                (
                    "filleul_lead",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="parrainages",
                        to="crm.lead",
                    ),
                ),
                (
                    "parrain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="parrainages_donnes",
                        to="crm.client",
                    ),
                ),
            ],
            options={
                "verbose_name": "Parrainage",
                "ordering": ["-date_creation"],
            },
        ),
    ]
