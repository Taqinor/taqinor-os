"""MRY8 — Fenêtres d'appel de la société sur `CompanyProfile`.

Neuf champs ADDITIFS, tous avec un défaut : aucune ligne existante n'est
touchée, aucun comportement ne change tant que `crm.horaires` n'est pas
appelé. Les défauts sont les règles réelles du Guide de Meryem (08:30-20:00,
pause du vendredi 11:30-15:00), pas des valeurs neutres ; la période de
Ramadan reste NULLE — jamais devinée.
"""
import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0081_cadence_relance_v2'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='appel_heure_debut',
            field=models.TimeField(
                default=datetime.time(8, 30),
                help_text='Heure locale à partir de laquelle on peut appeler.',
                verbose_name='Début des appels'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='appel_heure_fin',
            field=models.TimeField(
                default=datetime.time(20, 0),
                help_text="Heure locale après laquelle on n'appelle plus.",
                verbose_name='Fin des appels'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='vendredi_pause_debut',
            field=models.TimeField(
                default=datetime.time(11, 30),
                verbose_name='Vendredi — début de pause'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='vendredi_pause_fin',
            field=models.TimeField(
                default=datetime.time(15, 0),
                verbose_name='Vendredi — fin de pause'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='ramadan_debut',
            field=models.DateField(
                blank=True, null=True, verbose_name='Ramadan — début'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='ramadan_fin',
            field=models.DateField(
                blank=True, null=True, verbose_name='Ramadan — fin'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='ramadan_appel_debut',
            field=models.TimeField(
                default=datetime.time(10, 0),
                verbose_name='Ramadan — début des appels'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='ramadan_appel_fin',
            field=models.TimeField(
                default=datetime.time(14, 0),
                verbose_name='Ramadan — fin des appels'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='premier_contact_objectif_min',
            field=models.PositiveIntegerField(
                default=5,
                help_text="Minutes ouvrées maximum entre l'arrivée d'un lead "
                          'et la première prise de contact.',
                verbose_name='Objectif premier contact (minutes ouvrées)'),
        ),
    ]
