"""NTSRV7 - Affectation auto par competence (drapeau societe, OFF par defaut).

Additif : `affectation_par_competence` = False sur toutes les lignes
existantes -> comportement XSAV9 (round-robin par charge) inchange.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0055_ntsrv6_competences_categorie'),
    ]

    operations = [
        migrations.AddField(
            model_name='savslasettings',
            name='affectation_par_competence',
            field=models.BooleanField(
                default=False,
                help_text='Ne propose que des techniciens possédant les '
                          'compétences exigées par la catégorie du ticket '
                          '(repli sur la charge seule si aucun technicien '
                          'qualifié).',
                verbose_name='Affectation auto par compétence',
            ),
        ),
    ]
