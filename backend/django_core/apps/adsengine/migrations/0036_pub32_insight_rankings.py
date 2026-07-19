# PUB32 — diagnostics de classement Meta niveau ad (quality/engagement/conversion)
# sur InsightSnapshot : proxys négatifs lus par signal_guards.quality_ranking_guard.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0035_pub21_persist_killswitch_autonomy'),
    ]

    operations = [
        migrations.AddField(
            model_name='insightsnapshot',
            name='quality_ranking',
            field=models.CharField(
                blank=True, default='', max_length=16,
                verbose_name='Classement de qualité'),
        ),
        migrations.AddField(
            model_name='insightsnapshot',
            name='engagement_rate_ranking',
            field=models.CharField(
                blank=True, default='', max_length=16,
                verbose_name="Classement du taux d'engagement"),
        ),
        migrations.AddField(
            model_name='insightsnapshot',
            name='conversion_rate_ranking',
            field=models.CharField(
                blank=True, default='', max_length=16,
                verbose_name='Classement du taux de conversion'),
        ),
    ]
