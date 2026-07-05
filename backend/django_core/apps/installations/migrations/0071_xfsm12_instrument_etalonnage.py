from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0070_xfsm10_astreinte'),
    ]

    operations = [
        migrations.AddField(
            model_name='commissioningrecord',
            name='instrument_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
