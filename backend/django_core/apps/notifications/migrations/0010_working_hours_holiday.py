# FG5 — Calendrier ouvré par société : WorkingHoursConfig + Holiday.
# Additive migration only: two new tables, zero destructive changes.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0009_alter_notification_event_type_and_more"),
        ("authentication", "0010_customuser_supervisor"),
    ]

    operations = [
        # 1. WorkingHoursConfig — singleton par société (OneToOne).
        migrations.CreateModel(
            name="WorkingHoursConfig",
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
                    "working_days",
                    models.PositiveSmallIntegerField(
                        default=31,
                        verbose_name="Jours ouvrés (bitmask)",
                    ),
                ),
                (
                    "hours_per_day",
                    models.DecimalField(
                        decimal_places=2,
                        default="8.00",
                        max_digits=4,
                        verbose_name="Heures / jour",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notif_working_hours_config",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuration des heures ouvrées",
                "verbose_name_plural": "Configurations des heures ouvrées",
            },
        ),
        # 2. Holiday — jours fériés par société.
        migrations.CreateModel(
            name="Holiday",
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
                    "date",
                    models.DateField(verbose_name="Date"),
                ),
                (
                    "nom",
                    models.CharField(max_length=150, verbose_name="Nom"),
                ),
                (
                    "recurrent_annuel",
                    models.BooleanField(
                        default=False,
                        verbose_name="Récurrent chaque année",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notif_holidays",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Jour férié",
                "verbose_name_plural": "Jours fériés",
                "ordering": ["date"],
            },
        ),
        migrations.AddConstraint(
            model_name="holiday",
            constraint=models.UniqueConstraint(
                fields=["company", "date", "nom"],
                name="notif_holiday_company_date_nom_uniq",
            ),
        ),
    ]
