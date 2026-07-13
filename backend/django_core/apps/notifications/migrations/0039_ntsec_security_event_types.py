"""NTSEC12/13/30 — ajoute les types d'événement sécurité à ``EventType``.

Purement additif : les valeurs ``security_alert`` / ``security_change`` ne
changent aucune donnée existante ; l'AlterField ne fait qu'aligner la liste
``choices`` des trois champs ``event_type`` sur l'énumération à jour.
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0038_vx209_notification_archived"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="event_type",
            field=models.CharField(choices=EventType.choices, max_length=40),
        ),
        migrations.AlterField(
            model_name="notificationpreference",
            name="event_type",
            field=models.CharField(choices=EventType.choices, max_length=40),
        ),
        migrations.AlterField(
            model_name="notificationroutingrule",
            name="event_type",
            field=models.CharField(
                choices=EventType.choices, max_length=40,
                verbose_name="Type d'événement"),
        ),
    ]
