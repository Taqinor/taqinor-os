from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0007_campagneinnovation'),
    ]

    operations = [
        migrations.AddField(
            model_name='campagneinnovation',
            name='message_incitation',
            field=models.TextField(
                blank=True, default='', verbose_name="Message d'incitation"),
        ),
    ]
