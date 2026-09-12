# NTNRG32 — motif de limitation réseau (curtailment) sur ProductionReading.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0006_ntnrg27_certificatcarbone'),
    ]

    operations = [
        migrations.AddField(
            model_name='productionreading',
            name='motif_limitation',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
