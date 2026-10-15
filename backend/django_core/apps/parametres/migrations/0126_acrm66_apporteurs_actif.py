"""ACRM66 — réglage société ``apporteurs_actif`` (apporteurs et deals parqués).

ADDITIF : une colonne booléenne, défaut False (apporteurs parqués ; aucune
donnée supprimée). Réversible : ``python manage.py migrate parametres 0125``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0125_apar44_reglages_morts'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='apporteurs_actif',
            field=models.BooleanField(
                default=False,
                help_text='OFF = apporteurs parqués (routes 404, aucune '
                          'commission calculée, rien supprimé). ON = '
                          "comportement d'avant.",
                verbose_name="Apporteurs d'affaires et deals enregistrés "
                             'actifs'),
        ),
    ]
