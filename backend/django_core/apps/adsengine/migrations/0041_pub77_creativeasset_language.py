# PUB77 — Champ langue (fr / darija / amazigh) sur CreativeAsset : rend la
# performance créative comparable PAR LANGUE au reporting (leaderboard splité).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0040_pub76_asset_freshness'),
    ]

    operations = [
        migrations.AddField(
            model_name='creativeasset',
            name='language',
            field=models.CharField(blank=True, choices=[('fr', 'Français'), ('ar-ma', 'Darija (arabe marocain)'), ('amazigh', 'Amazigh')], default='', max_length=10, verbose_name='Langue'),
        ),
    ]
