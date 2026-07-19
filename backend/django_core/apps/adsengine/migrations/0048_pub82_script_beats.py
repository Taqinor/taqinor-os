# PUB82 — Rétention par scène : persiste les beats du script généré sur l'asset
# vidéo (script_beats) pour relier chaque percentile de rétention (p25/50/75/100)
# à la SCÈNE jouée (« la chute arrive à la scène du prix »).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0047_pub55_adengine_activity'),
    ]

    operations = [
        migrations.AddField(
            model_name='creativeasset',
            name='script_beats',
            field=models.JSONField(blank=True, default=list, verbose_name='Beats du script'),
        ),
    ]
