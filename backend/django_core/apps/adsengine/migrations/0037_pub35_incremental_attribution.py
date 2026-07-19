# PUB35 — attribution incrémentale native Meta (déploiement progressif) :
# lecture causale comparée aux résultats attribués, stockée additivement.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0036_pub32_insight_rankings'),
    ]

    operations = [
        migrations.AddField(
            model_name='insightsnapshot',
            name='incremental_attribution',
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name='Attribution incrémentale'),
        ),
    ]
