# Q2 — Lead roof-point capture + per-lead token (additive).
import uuid

from django.db import migrations, models


def _backfill_tokens(apps, schema_editor):
    """Give every existing lead a distinct token before the unique index lands.

    A unique callable default added in one step can collide on some backends;
    we add the column nullable, fill a fresh UUID per row, then enforce unique.
    """
    Lead = apps.get_model("crm", "Lead")
    for lead in Lead.objects.filter(token__isnull=True).iterator():
        lead.token = uuid.uuid4()
        lead.save(update_fields=["token"])


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0023_merge_20260621_0546"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="bill_kwh",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="roof_outline",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="roof_point",
            field=models.JSONField(blank=True, null=True),
        ),
        # Token: add nullable, backfill distinct values, then enforce unique.
        migrations.AddField(
            model_name="lead",
            name="token",
            field=models.UUIDField(
                db_index=True, default=uuid.uuid4, editable=False, null=True
            ),
        ),
        migrations.RunPython(_backfill_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="lead",
            name="token",
            field=models.UUIDField(
                db_index=True, default=uuid.uuid4, editable=False, unique=True
            ),
        ),
    ]
