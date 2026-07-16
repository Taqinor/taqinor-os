# VX212(a) — additif : raison courte "pourquoi je reçois ça" sur la ligne
# Notification (fermé, `NotificationReason` — vide = raison non classée,
# comportement historique inchangé).
from django.db import migrations, models

REASON_CHOICES = [
    ('assigne_a_vous', 'Assigné à vous'),
    ('manager', 'Vous êtes manager/responsable'),
    ('regle_de_routage', 'Règle de routage configurée'),
    ('vous_suivez', 'Vous suivez cet enregistrement'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0036_vx210_snooze_reveil'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='reason',
            field=models.CharField(
                blank=True, choices=REASON_CHOICES, default='', max_length=20),
        ),
    ]
