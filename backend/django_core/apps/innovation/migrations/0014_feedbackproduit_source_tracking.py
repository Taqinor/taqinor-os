from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0013_feedbackproduit_context'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedbackproduit',
            name='source_page',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Page source'),
        ),
        migrations.AddField(
            model_name='feedbackproduit',
            name='user_agent',
            field=models.CharField(
                blank=True, default='', max_length=500,
                verbose_name='User-Agent'),
        ),
    ]
