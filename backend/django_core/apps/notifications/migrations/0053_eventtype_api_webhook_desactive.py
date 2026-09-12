"""NTAPI11 — ajoute `api_webhook_desactive` à `EventType`.

La désactivation automatique d'un endpoint webhook mort porte sa PROPRE clé :
couper « alerte de sécurité » ou un digest ne doit jamais couper au passage le
seul signal qui prévient qu'une intégration cliente a cessé d'être livrée.
`AlterField(choices)` seul — aucune donnée touchée.
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0052_eventtype_bilan_hebdo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='event_type',
            field=models.CharField(choices=EventType.choices, max_length=40),
        ),
        migrations.AlterField(
            model_name='notificationpreference',
            name='event_type',
            field=models.CharField(choices=EventType.choices, max_length=40),
        ),
        migrations.AlterField(
            model_name='notificationroutingrule',
            name='event_type',
            field=models.CharField(
                choices=EventType.choices, max_length=40,
                verbose_name="Type d'événement"),
        ),
    ]
