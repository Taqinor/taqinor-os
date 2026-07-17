from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0008_campagneinnovation_message_incitation'),
    ]

    operations = [
        migrations.AddField(
            model_name='campagneinnovation',
            name='tag_auto',
            field=models.CharField(
                blank=True, default='', max_length=80,
                verbose_name='Tag automatique'),
        ),
    ]
