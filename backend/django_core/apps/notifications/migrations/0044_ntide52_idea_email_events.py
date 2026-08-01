"""NTIDE52 — ajoute les événements 'idea_received'/'idea_retenue'/
'idea_realisee' (gabarits e-mail des 3 étapes clés du cycle de vie d'une
idée, ``apps.innovation``) à ``EventType``.

Purement additif : l'AlterField ne fait qu'aligner la liste ``choices`` des
trois champs ``event_type`` sur l'énumération à jour (même patron que
0041_ntide16_idea_vote_event).
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0043_ntedu40_education_reinscription_relance_event'),
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
