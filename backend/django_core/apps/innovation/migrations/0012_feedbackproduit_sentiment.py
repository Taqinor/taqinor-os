from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0011_innovationsettings_feedback_digest'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedbackproduit',
            name='sentiment',
            field=models.CharField(
                blank=True,
                choices=[
                    ('positif', "+1 (je l'adore)"),
                    ('neutre', "Neutre (c'est ok)"),
                    ('negatif', "-1 (ça m'énerve)"),
                ],
                default='', max_length=10, verbose_name='Sentiment'),
        ),
    ]
