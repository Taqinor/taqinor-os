"""MRY0 (lot D) — ajoute ``lead_rattrape`` à ``EventType``.

« Lead Meta rattrapé par le pull (webhook muet) » : la seule alerte qui rende
visible l'incident AZIZ du 03/09/2026 (webhook silencieux 46 h). Purement
additif : l'``AlterField`` aligne la liste ``choices`` des trois champs
``event_type`` sur l'énumération à jour (même patron que
0049_crx27_dormance_sla_events).
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0049_crx27_dormance_sla_events'),
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
