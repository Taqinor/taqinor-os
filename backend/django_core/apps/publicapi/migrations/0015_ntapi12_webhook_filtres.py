from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0014_ntapi11_webhook_auto_disable'),
    ]

    operations = [
        migrations.AddField(
            model_name='webhook',
            name='filtres',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
