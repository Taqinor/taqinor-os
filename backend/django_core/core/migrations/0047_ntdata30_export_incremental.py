"""NTDATA30 — extraction incrémentale (high-watermark) des extraits planifiés.

Trois champs ADDITIFS sur ``ScheduledExport``, tous avec un défaut inerte :
``mode='complet'`` reproduit EXACTEMENT le comportement d'avant (extraction
complète à chaque passage), ``champ_curseur``/``dernier_curseur`` restent
vides. Aucun extrait existant ne change de comportement.

CHAÎNE : enchaîne explicitement sur la migration NTDATA29.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_ntdata29_export_snowflake'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduledexport',
            name='mode',
            field=models.CharField(
                choices=[('complet', 'Complet'),
                         ('incremental', 'Incrémental')],
                default='complet',
                help_text="« incrémental » n'extrait que les lignes dont le "
                          'champ curseur dépasse le dernier curseur '
                          'enregistré.',
                max_length=12, verbose_name="Mode d'extraction"),
        ),
        migrations.AddField(
            model_name='scheduledexport',
            name='champ_curseur',
            field=models.CharField(
                blank=True, default='',
                help_text='Champ monotone du dataset (ex. '
                          'updated_at/created_at). Doit appartenir à la liste '
                          'blanche du dataset.',
                max_length=80, verbose_name='Champ curseur'),
        ),
        migrations.AddField(
            model_name='scheduledexport',
            name='dernier_curseur',
            field=models.CharField(
                blank=True, default='',
                help_text='Borne haute atteinte au dernier passage (posée par '
                          'le runner, jamais saisie).',
                max_length=64, verbose_name='Dernier curseur'),
        ),
    ]
