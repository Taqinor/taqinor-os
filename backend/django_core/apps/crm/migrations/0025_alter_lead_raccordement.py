# Additive choices change: adds the 'inconnu' ("Je ne sais pas") raccordement
# option for the toiture-3D website intake. No data change — existing
# 'monophase'/'triphase' values stay intact.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0024_lead_bill_kwh_lead_roof_outline_lead_roof_point_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="raccordement",
            field=models.CharField(
                blank=True,
                choices=[
                    ("monophase", "Monophasé"),
                    ("triphase", "Triphasé"),
                    ("inconnu", "Je ne sais pas"),
                ],
                max_length=12,
                null=True,
            ),
        ),
    ]
