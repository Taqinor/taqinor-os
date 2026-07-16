# QX30be — moteur de relance déclenchée par le comportement : mémorise les
# déclencheurs d'engagement déjà notifiés (idempotence). Additif/nullable.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0080_qx23_marge_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharelink',
            name='engagement_triggers_fired',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
