# Generated for XPLT10 — tokenized public dashboard sharing + fine internal sharing.

import core.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("core", "0016_apiusageplan_changelogentry_apiusagerecord_backuprun_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PartageDashboard",
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
                    "token",
                    models.CharField(
                        default=core.models._default_dashboard_partage_token,
                        editable=False,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="expire le"
                    ),
                ),
                ("actif", models.BooleanField(default=True, verbose_name="actif")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_partages",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dashboard_partages_crees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "dashboard",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="partages_publics",
                        to="core.dashboard",
                        verbose_name="Dashboard",
                    ),
                ),
            ],
            options={
                "verbose_name": "Partage public de dashboard",
                "verbose_name_plural": "Partages publics de dashboard",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="DashboardPartageInterne",
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
                ("role", models.CharField(blank=True, default="", max_length=20)),
                (
                    "niveau",
                    models.CharField(
                        choices=[("lecture", "Lecture"), ("edition", "Édition")],
                        default="lecture",
                        max_length=10,
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_partages_internes",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "dashboard",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="partages_internes",
                        to="core.dashboard",
                        verbose_name="Dashboard",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dashboard_partages_recus",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Partage interne de dashboard",
                "verbose_name_plural": "Partages internes de dashboard",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="dashboardpartageinterne",
            constraint=models.UniqueConstraint(
                condition=models.Q(("utilisateur__isnull", False)),
                fields=("dashboard", "utilisateur"),
                name="core_dashpartage_interne_dash_user_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="dashboardpartageinterne",
            constraint=models.UniqueConstraint(
                condition=~models.Q(role=""),
                fields=("dashboard", "role"),
                name="core_dashpartage_interne_dash_role_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="partagedashboard",
            index=models.Index(
                fields=["company", "dashboard"],
                name="core_dashpartage_co_dash_idx",
            ),
        ),
    ]
