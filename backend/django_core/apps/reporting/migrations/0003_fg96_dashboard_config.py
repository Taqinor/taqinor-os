# Generated for FG96 — per-user/per-role dashboard config.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("reporting", "0002_fg91_savedreport_pinned"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardConfig",
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
                ("menu_tier", models.CharField(blank=True, default="", max_length=20)),
                ("cards", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reporting_dashboard_configs",
                        to="authentication.company",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reporting_dashboard_configs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuration tableau de bord",
                "verbose_name_plural": "Configurations tableau de bord",
                "ordering": ["-updated_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["company", "user"],
                        name="rpt_dashcfg_co_user_idx",
                    ),
                    models.Index(
                        fields=["company", "menu_tier"],
                        name="rpt_dashcfg_co_tier_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(user__isnull=False),
                        fields=["company", "user"],
                        name="rpt_dashcfg_co_user_uniq",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(user__isnull=True),
                        fields=["company", "menu_tier"],
                        name="rpt_dashcfg_co_tier_uniq",
                    ),
                ],
            },
        ),
    ]
