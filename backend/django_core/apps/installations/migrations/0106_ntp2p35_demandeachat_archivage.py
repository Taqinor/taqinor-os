"""NTP2P35 — archivage (jamais suppression) des brouillons de demande d'achat.

Ajoute ``DemandeAchat.archivee`` / ``epinglee`` (défaut False) et
``date_archivage`` (nullable). ADDITIF STRICT : aux valeurs par défaut, aucune
réquisition existante ne change d'état ni ne disparaît d'aucune liste — seule
la tâche planifiée ``installations.purger_demandes_achat_brouillon`` peut
poser ``archivee=True``, et jamais sur un brouillon épinglé.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0105_cht23_stagemodele_photos_checklist_min'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeachat',
            name='archivee',
            field=models.BooleanField(
                default=False,
                help_text='Retirée des listes actives par défaut ; jamais '
                          'supprimée.',
                verbose_name='Archivée'),
        ),
        migrations.AddField(
            model_name='demandeachat',
            name='epinglee',
            field=models.BooleanField(
                default=False,
                help_text="Un brouillon épinglé n'est jamais archivé "
                          'automatiquement.',
                verbose_name='Épinglée'),
        ),
        migrations.AddField(
            model_name='demandeachat',
            name='date_archivage',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Date d'archivage"),
        ),
    ]
