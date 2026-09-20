"""NTWFL18 — ajoute l'événement 'dossier_echeance_depassee' à ``EventType``.

Purement additif : l'AlterField ne fait qu'aligner la liste ``choices`` des
trois champs ``event_type`` sur l'énumération à jour (même patron que
0062_eventtype_notifications_portail)."""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0063_holiday_pays'),
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
