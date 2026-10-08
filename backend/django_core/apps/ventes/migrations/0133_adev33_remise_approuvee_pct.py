# ADEV33 — profondeur de remise approuvée (AddField nullable, revertable).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0132_acal102_backfill_production_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='remise_approuvee_pct',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
    ]
