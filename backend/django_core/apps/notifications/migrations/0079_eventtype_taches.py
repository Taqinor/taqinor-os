"""TCH20 — ajoute les quatre événements du gestionnaire de tâches personnel
(``taches_plan_du_jour``, ``taches_bilan_soir``, ``taches_relance``,
``taches_rappel``) à ``EventType``.

Purement additif : l'AlterField ne fait qu'aligner la liste ``choices`` des
trois champs ``event_type`` sur l'énumération à jour (même patron que
0078_eventtype_travail_de_fond_echoue). Écrite à la main : les migrations
précédentes lisent ``EventType.choices`` vivant, donc ``makemigrations`` ne
voit aucun écart (« No changes detected »)."""
from django.db import migrations, models

from apps.notifications.models import EventType


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0078_eventtype_travail_de_fond_echoue'),
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
