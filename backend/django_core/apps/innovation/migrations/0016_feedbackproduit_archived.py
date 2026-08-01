from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0015_feedbackproduit_starred'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedbackproduit',
            name='archived',
            field=models.BooleanField(
                default=False, verbose_name='Masqué (modération)'),
        ),
    ]
