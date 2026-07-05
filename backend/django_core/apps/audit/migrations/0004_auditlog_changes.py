# YHARD3 — diff structuré additif sur AuditLog (reconstruction as-of).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0003_auditlog_notify_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="changes",
            field=models.JSONField(blank=True, null=True, verbose_name="Diff structuré"),
        ),
    ]
