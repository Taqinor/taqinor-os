"""AMOT97 (D-ACI-15=a) — scénarios de sensibilité C&I SEEDÉS.

Le défaut de ``TariffSettings.sensibilites_ci`` devient la liste sourcée
``tariff.SENSIBILITES_CI_DEFAUT`` (nouvelles sociétés) et les réglages
existants restés VIDES la reçoivent ; une liste déjà saisie n'est jamais
touchée. Réversible : le retour remet à vide les seules listes encore égales
aux scénarios seedés (``python manage.py migrate parametres 0127``).
"""
from django.db import migrations, models

import apps.parametres.tariff


def _seeder(apps, schema_editor):
    from apps.parametres.tariff import sensibilites_ci_par_defaut
    TariffSettings = apps.get_model('parametres', 'TariffSettings')
    for reglage in TariffSettings.objects.all().only('pk', 'sensibilites_ci'):
        if not reglage.sensibilites_ci:
            reglage.sensibilites_ci = sensibilites_ci_par_defaut()
            reglage.save(update_fields=['sensibilites_ci'])


def _retirer(apps, schema_editor):
    from apps.parametres.tariff import sensibilites_ci_par_defaut
    TariffSettings = apps.get_model('parametres', 'TariffSettings')
    for reglage in TariffSettings.objects.all().only('pk', 'sensibilites_ci'):
        if reglage.sensibilites_ci == sensibilites_ci_par_defaut():
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
                blank=True,
                default=apps.parametres.tariff.sensibilites_ci_par_defaut,
                help_text='Liste [{cle (indexation_tarif|degradation|tarif_kwh|'
                          'production), variation_pct, source}] — scénarios '
                          'seedés sourcés, modifiables.',
                verbose_name='Scénarios de sensibilité C&I'),
        ),
        migrations.RunPython(_seeder, _retirer),
    ]
