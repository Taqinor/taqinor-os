from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0025_xsav23_reponsetype'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='auto_cloture_jours',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
