from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0013_ntapi13_bulkjob'),
    ]

    operations = [
        migrations.AddField(
            model_name='webhook',
            name='disabled_reason',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='webhook',
            name='disabled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
