# XRH12 — Géofence de pointage chantier (optionnelle) + ReglageRH.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0048_correction_pointage"),
    ]

    operations = [
        migrations.AddField(
            model_name="presencechantier",
            name="gps_lat",
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="presencechantier",
            name="gps_lng",
            field=models.DecimalField(
                blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="presencechantier",
            name="hors_zone",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="ReglageRH",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("geofence_metres", models.PositiveIntegerField(
                    blank=True, null=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                ("company", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_reglage", to="authentication.company")),
            ],
            options={
                "verbose_name": "Réglage RH",
                "verbose_name_plural": "Réglages RH",
            },
        ),
    ]
