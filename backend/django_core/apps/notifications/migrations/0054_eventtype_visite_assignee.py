"""VTA7 — ajoute `visite_terrain_assignee` à `EventType`.

L'assignation d'une visite porte sa PROPRE clé plutôt que d'emprunter celle du
feu vert : c'est le seul message qui arrive AVANT la visite, et couper l'un ne
doit pas couper l'autre dans les préférences. `AlterField(choices)` seul —
aucune donnée touchée (les `choices` ne sont pas contraints en base).
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0053_vta5_liens_visites'),
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
