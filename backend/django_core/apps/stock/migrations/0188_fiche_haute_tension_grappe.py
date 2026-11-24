"""HT24 — fiche technique HAUTE TENSION (fondateur 24/11/2026, « With battery
now also picks from HV inverters ») : grappe en série d'une batterie (bornes
de modules en série, tension d'un module, grappes en parallèle) et port
batterie d'un hybride (nombre d'entrées batterie, appareils en parallèle).

Additive : six ``AddField`` nullables, aucune donnée écrite ; réversible.
"""
import decimal

import django.core.validators
from django.db import migrations, models


def _entier_min_1(help_text):
    return models.PositiveSmallIntegerField(
        blank=True, null=True, help_text=help_text,
        validators=[django.core.validators.MinValueValidator(1)])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0187_dyness_5kwh_garantie_10_ans'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_serie_min_modules',
            field=_entier_min_1(
                'Batterie haute tension — nombre MINIMUM de modules en '
                'série dans une grappe (fiche constructeur). Vide = pack '
                'basse tension ou non publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_serie_max_modules',
            field=_entier_min_1(
                'Batterie haute tension — nombre MAXIMUM de modules en '
                'série dans une grappe avec un onduleur hybride (fiche '
                'constructeur). Vide = non publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_v_module',
            field=models.DecimalField(
                blank=True, decimal_places=1, max_digits=5, null=True,
                validators=[django.core.validators.MinValueValidator(
                    decimal.Decimal('0.1'))],
                help_text='Batterie haute tension — tension nominale d’UN '
                          'module (V) ; la grappe vaut n × cette tension. '
                          'Vide = non publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_grappes_max_parallele',
            field=_entier_min_1(
                'Batterie haute tension — nombre maximum de grappes en '
                'parallèle (fiche constructeur). Vide = non publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_bat_nb_entrees',
            field=_entier_min_1(
                "Onduleur hybride — nombre d'entrées batterie (« Number "
                'of Battery Input »). Vide = non publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_max_parallele',
            field=_entier_min_1(
                'Onduleur hybride — nombre maximum d’appareils en '
                'parallèle publié par la fiche. Vide = non publié.'),
        ),
    ]
