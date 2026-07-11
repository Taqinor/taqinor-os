# QX15 — Callback SLA clock measures the right thing. Additive + nullable
# timestamp of WHEN contact_preference was set (distinct from date_creation),
# so the SLA-breach selector can measure from the right moment instead of
# instantly flagging an old lead as "SLA breached" the moment it asks for a
# callback.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0051_lead_tiers"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="contact_preference_set_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
