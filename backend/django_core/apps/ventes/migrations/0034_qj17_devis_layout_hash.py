"""QJ17 — add layout_hash to Devis for from-layout idempotency deduplication."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0033_qj16_devis_preset'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='layout_hash',
            field=models.CharField(
                blank=True, db_index=True, max_length=64, null=True),
        ),
    ]
