"""NTIDE16 — ajoute l'événement 'idea_vote' (vote reçu sur une idée
interne, ``apps.innovation``) à ``EventType``.

Purement additif : l'AlterField ne fait qu'aligner la liste ``choices`` des
trois champs ``event_type`` sur l'énumération à jour (même patron que
0039_ntsec_security_event_types).
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0040_yhard1_encrypt_vapid_private_key'),
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
