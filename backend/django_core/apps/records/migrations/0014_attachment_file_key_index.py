# ADOC193 — index sur Attachment.file_key : le registre des détenteurs de
# clés (records.cles_stockage) interroge cette colonne avant tout effacement.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0013_vx210_snooze_trigger_event'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='file_key',
            field=models.CharField(db_index=True, max_length=500),
        ),
    ]
