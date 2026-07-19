# PUB20 — santé du token Meta : détection + alerte, jamais un dashboard figé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0033_guardrailconfig_health_creative_weight_ctr_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='metaconnection',
            name='token_expires_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Expiration du token'),
        ),
        migrations.AddField(
            model_name='metaconnection',
            name='token_invalid',
            field=models.BooleanField(
                default=False, verbose_name='Token invalide (détecté)'),
        ),
        migrations.AddField(
            model_name='metaconnection',
            name='token_invalid_at',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name='Détection du token invalide'),
        ),
        migrations.AlterField(
            model_name='enginealert',
            name='alert_type',
            field=models.CharField(
                choices=[
                    ('anomalie', 'Anomalie'),
                    ('garde_fou', 'Violation de garde-fou'),
                    ('regle_inoperante', 'Règle inopérante'),
                    ('token_invalide', 'Token Meta invalide'),
                ],
                max_length=20, verbose_name="Type d'alerte"),
        ),
    ]
