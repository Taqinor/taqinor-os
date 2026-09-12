"""CHT9 — désenchevêtre ``CHANTIER_DUE`` : ajoute 5 ``EventType``.

``CHANTIER_DUE`` (« Chantier à installer », l'alerte de date de pose/météo de
``apps.installations.tasks``) servait aussi, par facilité, à TROIS faits
métier sans rapport (réassignation d'intervention, annulation d'intervention,
tranche d'échéancier à facturer) : couper ``CHANTIER_DUE`` dans les
préférences coupait ces trois-là par ricochet, invisible dans l'écran de
préférences. Ajoute leurs clés propres ``intervention_assignee`` (NOUVEAU —
notifie enfin le technicien affecté/réaffecté à une intervention),
``intervention_replanifiee``, ``intervention_annulee``,
``tranche_a_facturer``, et ``chantier_materiel_confirme`` (CHT15 — BC
rattaché à un chantier confirmé). ``AlterField(choices)`` seul sur les 3
modèles qui portent l'énumération — aucune donnée touchée.
"""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0052_eventtype_bilan_hebdo'),
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
