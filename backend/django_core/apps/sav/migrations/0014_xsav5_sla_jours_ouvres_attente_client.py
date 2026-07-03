from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0013_xsav4_sla_notifications_client'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='sla_jours_ouvres',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ticket',
            name='en_attente_client',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ticket',
            name='attente_depuis',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='jours_pause',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
