import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0006_eng9_pause_kind"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeeklyBrief",
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
                    "period_start",
                    models.DateField(verbose_name="Début de période"),
                ),
                (
                    "period_end",
                    models.DateField(verbose_name="Fin de période"),
                ),
                (
                    "data",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Chiffres (JSON)"),
                ),
                (
                    "markdown",
                    models.TextField(
                        blank=True, default="",
                        verbose_name="Rendu markdown (FR)"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
            ],
            options={
                "verbose_name": "Brief hebdomadaire",
                "verbose_name_plural": "Briefs hebdomadaires",
                "ordering": ["-period_start", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="weeklybrief",
            constraint=models.UniqueConstraint(
                fields=("company", "period_start"),
                name="uniq_adsengine_weekly_brief"),
        ),
    ]
