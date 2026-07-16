import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0008_enginealert"),
    ]

    operations = [
        migrations.CreateModel(
            name="CreativeAsset",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset_type",
                    models.CharField(
                        choices=[
                            ("reel", "Reel (vidéo verticale)"),
                            ("static", "Statique (image)"),
                            ("explainer", "Explainer animé"),
                        ],
                        max_length=12, verbose_name="Type"),
                ),
                (
                    "file_key",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Clé MinIO"),
                ),
                (
                    "source_lane",
                    models.CharField(
                        blank=True, default="",
                        help_text="Origine (upload / fal / templated / "
                                  "zapcap / …).",
                        max_length=40, verbose_name="Lane source"),
                ),
                (
                    "cost_cents",
                    models.PositiveIntegerField(
                        default=0,
                        verbose_name="Coût de production (centimes)"),
                ),
                (
                    "policy_stamp",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Tampon policy (check-list)"),
                ),
                (
                    "perf",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Performance (remontée des insights)"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="variants",
                        to="adsengine.creativeasset",
                        verbose_name="Asset parent (variante)"),
                ),
            ],
            options={
                "verbose_name": "Asset créatif",
                "verbose_name_plural": "Assets créatifs",
                "ordering": ["-created_at"],
            },
        ),
    ]
