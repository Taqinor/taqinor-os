from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0014_xsav5_sla_jours_ouvres_attente_client'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='sla_warning_days',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='savslasettings',
            name='escalade_activee',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ticket',
            name='sla_pre_alert_notifiee',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ticket',
            name='sla_escalade_notifiee',
            field=models.BooleanField(default=False),
        ),
    ]
