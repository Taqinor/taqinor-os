# QX23be — instantané de marge (interne, manager-only). Additif/nullable.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0079_qx9_esign_evidence'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='marge_snapshot',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                verbose_name='Marge HT figée (interne, manager-only)'),
        ),
    ]
