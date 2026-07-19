# PUB21 — kill-switch + autonomie persistés en base (source de vérité), le
# cache n'étant plus qu'un accélérateur : un flush/restart ne perd plus l'état.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0034_pub20_token_health'),
    ]

    operations = [
        migrations.AddField(
            model_name='guardrailconfig',
            name='kill_switch_engaged',
            field=models.BooleanField(
                default=False, verbose_name='Interrupteur global engagé'),
        ),
        migrations.AddField(
            model_name='guardrailconfig',
            name='kill_switch_engaged_at',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Engagement de l'interrupteur"),
        ),
        migrations.AddField(
            model_name='guardrailconfig',
            name='kill_switch_reason',
            field=models.TextField(
                blank=True, default='',
                verbose_name="Motif de l'interrupteur"),
        ),
        migrations.AddField(
            model_name='guardrailconfig',
            name='autonomy_active',
            field=models.BooleanField(
                default=False, verbose_name='Mode autonome activé'),
        ),
    ]
