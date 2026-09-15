"""VISITE-CADENCE — ajoute `visite_retour_terrain` et
`visite_terrain_a_valider` à ``EventType``.

Les deux messages qui manquaient APRÈS la visite technique : le RESPONSABLE du
lead apprend qu'il doit rappeler sous 24-48 h, et le bureau d'études qu'une
visite terminée attend son feu vert. Deux clés distinctes (deux publics, deux
suites) pour qu'on puisse couper l'une sans l'autre dans les préférences.

Purement additif : l'``AlterField`` ne fait qu'aligner la liste ``choices`` des
trois champs ``event_type`` sur l'énumération à jour (même patron que
0054/0055/0056) — les ``choices`` ne sont pas contraints en base, aucune donnée
n'est touchée.
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0056_eventtype_usage_quota_seuil_franchi'),
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
