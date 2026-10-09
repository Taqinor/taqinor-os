"""APAR58 — ajoute l'événement 'adsengine_alert' à ``EventType``.

Purement additif : l'AlterField ne fait qu'aligner la liste ``choices`` des
trois champs ``event_type`` sur l'énumération à jour (même patron que
0064_eventtype_dossier_echeance_depassee)."""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0070_eventtype_appointment_reminder'),
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
