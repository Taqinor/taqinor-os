"""AMOT97 (D-ACI-15=a) — 4 scénarios de sensibilité C&I SEEDÉS et sourcés.

ADDITIF : le défaut de ``TariffSettings.sensibilites_ci`` devient la liste
``tariff.SENSIBILITES_CI_DEFAUT`` (nouvelles sociétés) et les réglages
EXISTANTS dont la liste est vide la reçoivent ; une liste déjà saisie n'est
jamais touchée. Réversible : ``python manage.py migrate parametres 0127``
(les listes restées égales au seed redeviennent vides).
"""
from django.db import migrations, models

import apps.parametres.tariff


def _seeder(apps, schema_editor):
    from apps.parametres.tariff import sensibilites_ci_defaut
    modele = apps.get_model('parametres', 'TariffSettings')
    for reglage in modele.objects.all():
        if not reglage.sensibilites_ci:
            reglage.sensibilites_ci = sensibilites_ci_defaut()
            reglage.save(update_fields=['sensibilites_ci'])


def _retirer(apps, schema_editor):
    from apps.parametres.tariff import sensibilites_ci_defaut
    modele = apps.get_model('parametres', 'TariffSettings')
    for reglage in modele.objects.all():
        if reglage.sensibilites_ci == sensibilites_ci_defaut():
            reglage.sensibilites_ci = []
            reglage.save(update_fields=['sensibilites_ci'])


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0127_amot96_entretien_minimum'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tariffsettings',
            name='sensibilites_ci',
            field=models.JSONField(
                blank=True, default=apps.parametres.tariff.sensibilites_ci_defaut,
                help_text='Liste [{cle (indexation_tarif|degradation|tarif_kwh|'
                          'production|contribution_art13), variation_pct, '
                          'source}] — 4 scénarios sourcés par défaut (AMOT97).',
                verbose_name='Scénarios de sensibilité C&I'),
        ),
        migrations.RunPython(_seeder, _retirer),
    ]
