"""AMSG78 (C-AMSG-039) — ``Notification.sans_email`` : le drapeau ``skip_email``
survit au report hors fenêtre (additif, défaut faux = comportement des lignes
existantes)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0076_eventtype_candidature_trust_center'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='sans_email',
            field=models.BooleanField(default=False),
        ),
    ]
