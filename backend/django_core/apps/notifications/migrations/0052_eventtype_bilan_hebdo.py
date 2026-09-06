"""MRY21 — ajoute `crm_bilan_hebdo` à `EventType`.

Le bilan hebdomadaire du moteur de relances porte sa PROPRE clé plutôt que
d'emprunter `digest` : couper le récapitulatif générique ne doit pas couper au
passage le pilotage commercial. `AlterField(choices)` seul — aucune donnée
touchée.
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0051_eventtype_relances'),
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
