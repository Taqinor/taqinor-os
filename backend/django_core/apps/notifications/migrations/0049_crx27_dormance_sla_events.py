"""CRX27 — ajoute les deux événements dédiés du CRM ('compte_a_reactiver',
'lead_non_contacte') à ``EventType``.

Ils empruntaient jusqu'ici la clé ``lead_assigned`` : couper « Nouveau lead
assigné » dans ses préférences coupait donc aussi la dormance des comptes et
l'escalade SLA des leads non contactés.

Purement additif : l'AlterField ne fait qu'aligner la liste ``choices`` des
trois champs ``event_type`` sur l'énumération à jour (même patron que
0048_t_trace_visiteur_events).
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0048_t_trace_visiteur_events'),
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
