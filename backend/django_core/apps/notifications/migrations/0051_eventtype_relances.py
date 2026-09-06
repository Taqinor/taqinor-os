"""MRY17 — `relance_due` et `premier_contact_depasse` entrent dans `EventType`.

Purement additif (`AlterField(choices)` sur les trois champs `event_type`).
Deux clés DISTINCTES : couper le digest quotidien des relances ne doit jamais
couper au passage l'alerte de speed-to-lead, qui est critique.
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0050_eventtype_lead_rattrape'),
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
