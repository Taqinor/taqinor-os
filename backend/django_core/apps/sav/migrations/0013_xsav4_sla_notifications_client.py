from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0012_xsav3_ticket_devis_id_ext'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='notifications_client_sav',
            field=models.BooleanField(default=False),
        ),
    ]
