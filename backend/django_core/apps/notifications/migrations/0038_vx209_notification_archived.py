# VX209(c) — additif : `archived` sur la ligne Notification pour la purge
# périodique (lues > 60 j supprimées, non-lues > 60 j archivées plutôt que
# supprimées). Défaut `False` — comportement historique inchangé pour toute
# notification existante.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0037_notification_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='archived',
            field=models.BooleanField(default=False),
        ),
    ]
