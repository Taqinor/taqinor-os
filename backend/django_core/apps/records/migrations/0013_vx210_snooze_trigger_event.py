# VX210(a)/(c) — additif : réveil actif du snooze (VX85), déclenché par
# l'échéance OU un événement métier fermé (`snooze_trigger_event`).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0012_activity_snoozed_until'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='snoozed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='activity',
            name='snooze_trigger_event',
            field=models.CharField(
                blank=True, default='', max_length=100,
                verbose_name='Déclencheur de réveil (VX210)'),
        ),
    ]
