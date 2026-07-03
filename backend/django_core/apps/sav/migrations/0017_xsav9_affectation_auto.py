from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0016_xsav7_contrat_sla_overrides'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='affectation_auto_sav',
            field=models.BooleanField(default=False),
        ),
    ]
