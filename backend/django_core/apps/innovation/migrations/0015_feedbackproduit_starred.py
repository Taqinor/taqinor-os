from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0014_feedbackproduit_source_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedbackproduit',
            name='starred',
            field=models.BooleanField(
                default=False, verbose_name='Marqué important (étoilé)'),
        ),
    ]
