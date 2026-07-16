import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GuardrailConfig",
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
                    "daily_budget_ceiling_mad",
                    models.PositiveIntegerField(
                        default=100,
                        verbose_name="Plafond budget quotidien (MAD)"),
                ),
                (
                    "weekly_change_pct_max",
                    models.PositiveIntegerField(
                        default=20,
                        verbose_name="Variation hebdomadaire max (%)"),
                ),
                (
                    "anomaly_window_hours",
                    models.PositiveIntegerField(
                        default=48,
                        verbose_name="Fenêtre de détection d'anomalie (heures)"),
                ),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adsengine_guardrail_config",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
            ],
            options={
                "verbose_name": "Garde-fous publicitaires",
                "verbose_name_plural": "Garde-fous publicitaires",
                "ordering": ["-created_at"],
            },
        ),
    ]
