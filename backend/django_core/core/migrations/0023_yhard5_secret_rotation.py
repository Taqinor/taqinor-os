# YHARD5 — gouvernance des secrets & suivi de rotation (additif, key-agnostique).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0022_yopsb10_retentionrun"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationconfig",
            name="secret_last_rotated_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Dernière rotation du secret"),
        ),
        migrations.AddField(
            model_name="integrationconfig",
            name="rotation_period_days",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Période de rotation (jours)"),
        ),
        migrations.AddField(
            model_name="integrationconfig",
            name="secret_owner",
            field=models.CharField(
                blank=True, default="", max_length=120,
                verbose_name="Propriétaire du secret"),
        ),
    ]
