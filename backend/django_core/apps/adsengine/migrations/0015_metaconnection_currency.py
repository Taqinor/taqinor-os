from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0014_flightphase_tested_variable_len'),
    ]

    operations = [
        migrations.AddField(
            model_name='metaconnection',
            name='currency',
            field=models.CharField(
                blank=True, default='', max_length=8,
                verbose_name='Devise du compte'),
        ),
    ]
