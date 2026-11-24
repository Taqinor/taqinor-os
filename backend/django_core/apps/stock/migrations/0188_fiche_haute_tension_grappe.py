"""HT24 — fiche technique HAUTE TENSION (fondateur 24/11/2026, « With battery
now also picks from HV inverters ») : grappe en série d'une batterie (bornes
de modules en série, tension d'un module, grappes en parallèle) et port
batterie d'un hybride (nombre d'entrées batterie, appareils en parallèle,
courant maximal par entrée) ; rôles C&I ``boitier_batterie_ht`` (boîtier
de contrôle de la batterie, Deye BOS-B-PDU-2-A) et ``rack_batterie_ht`` (rack
et câblage de puissance d'une grappe).

Additive : sept ``AddField`` nullables et un ``AlterField`` de ``choices``
(aucun effet SQL), aucune donnée écrite ; réversible.
"""
import decimal

import django.core.validators
from django.db import migrations, models

#: Vocabulaire ``Produit.role_ci`` FIGÉ à cette migration (celui de 0172 +
#: ``boitier_batterie_ht``, ``rack_batterie_ht``) — jamais importé du code vivant.
ROLES_CI = [
    'onduleur_string_tri', 'compteur_injection', 'controleur_injection',
    'logger_supervision', 'structure_ci', 'cable_ac', 'protection_ac',
    'protection_dc', 'coffret_ac', 'coffret_dc', 'mise_a_la_terre',
    'cellule_mt', 'etudes_ingenierie', 'pose_structure', 'pose_modules',
    'raccordement_ac', 'mise_en_service', 'dossier_raccordement',
    'levage_acces', 'transport_ci', 'om_ci', 'batterie_ci',
    'onduleur_string_mono', 'cable_dc', 'boitier_batterie_ht', 'rack_batterie_ht',
]


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
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_bat_i_max_a',
            field=models.DecimalField(
                blank=True, decimal_places=1, max_digits=6, null=True,
                validators=[django.core.validators.MinValueValidator(
                    decimal.Decimal('0.1'))],
                help_text='Onduleur hybride — courant maximal de charge/'
                          'décharge PAR ENTRÉE batterie (A). Vide = non publié.'),
        ),
        # Rôles C&I ``boitier_batterie_ht`` et ``rack_batterie_ht`` (accessoires
        # d'une grappe de batterie haute tension) ajoutés en fin de ``ROLES_CI`` :
        # seuls les ``choices`` changent (aucun effet SQL).
        migrations.AlterField(
            model_name='produit',
            name='role_ci',
            field=models.CharField(
                blank=True, choices=[(r, r) for r in ROLES_CI], db_index=True,
                default='',
                help_text="Rôle DÉCLARÉ dans une composition commerciale/"
                          "industrielle (compteur_injection, structure_ci…). "
                          "Vide = non déclaré.",
                max_length=32, verbose_name='Rôle C&I'),
        ),
    ]
