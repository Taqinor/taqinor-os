# XSAL9 — Client.parent self-FK (account hierarchy / consolidation).
# Additive + nullable, reversible via the automatic RemoveField reverse.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0046_xsal7_lead_forecast_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="parent",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="filiales", to="crm.client",
                help_text="Rattache ce client à une société mère "
                          "(consolidation CA groupe). Même société "
                          "uniquement ; jamais de cycle.",
                verbose_name="Société mère",
            ),
        ),
    ]
