"""NTSRV8 - Capacite d'une equipe de maintenance (additif, optionnel).

NULL par defaut : aucune equipe existante ne declare de capacite, donc aucun
debordement n'est jamais calcule -> comportement actuel inchange.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0056_ntsrv7_affectation_competence'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipemaintenance',
            name='capacite_max_tickets_ouverts',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Nombre maximum de tickets ouverts simultanés pour '
                          'cette équipe. Vide = aucune limite (aucune '
                          'proposition de débordement).',
                null=True,
                verbose_name='Capacité (tickets ouverts)',
            ),
        ),
    ]
