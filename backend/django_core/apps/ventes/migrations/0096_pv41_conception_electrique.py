# PV41 — conception électrique persistée sur le devis (additive, revertable).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0095_ntcpq14_18_20_modeles_cpq'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='electrical_design',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='devis',
            name='electrical_design_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64,
                                   null=True),
        ),
    ]
