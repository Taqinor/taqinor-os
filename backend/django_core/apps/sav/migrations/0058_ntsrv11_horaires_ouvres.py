"""NTSRV11 - Fenetre HORAIRE ouvree configurable (additif, OFF par defaut).

`horaires_ouvres` NULL + `sla_heures_ouvrees_actif` False sur toutes les
lignes existantes -> calcul SLA strictement inchange (XSAV5 : jours seuls).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0057_ntsrv8_capacite_equipe'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='horaires_ouvres',
            field=models.JSONField(
                blank=True,
                help_text="Fenêtre de travail : {'jours': [0=lundi … "
                          "6=dimanche], 'debut': 'HH:MM', 'fin': 'HH:MM'}. "
                          'Vide = lun-ven 8h-18h.',
                null=True,
                verbose_name='Horaires ouvrés',
            ),
        ),
        migrations.AddField(
            model_name='savslasettings',
            name='sla_heures_ouvrees_actif',
            field=models.BooleanField(
                default=False,
                help_text='Exclut aussi les HEURES hors plage du décompte SLA '
                          '(pas seulement les jours). OFF = comportement '
                          'actuel.',
                verbose_name='SLA en heures ouvrées',
            ),
        ),
    ]
