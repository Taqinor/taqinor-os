# YSERV5 — Génération automatique planifiée des visites préventives dues.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0037_xctr4_ticket_couverture'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='generation_auto_visites',
            field=models.BooleanField(
                default=False,
                help_text='Génère chaque nuit les visites préventives dues '
                          '(beat), sans action manuelle.',
                verbose_name='Génération automatique des visites'),
        ),
        migrations.AddField(
            model_name='savslasettings',
            name='visites_avance_jours',
            field=models.PositiveIntegerField(
                default=7,
                help_text='Nombre de jours avant échéance où une visite due '
                          'est matérialisée par la tâche automatique.',
                verbose_name='Avance de génération (jours)'),
        ),
    ]
