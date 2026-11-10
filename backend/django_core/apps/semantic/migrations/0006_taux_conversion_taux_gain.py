"""ASOC72 (D-AANA-1) — `taux_conversion` lit LE taux de gain du reporting
(adaptateur `reporting.taux_gain` : gagnés ÷ NON perdus) au lieu de signés ÷
toutes les pistes. Données seules, patron de 0005 : seule une définition dont
la mesure est EXACTEMENT l'ancien défaut est réalignée (version dernier + 1) ;
une mesure retouchée n'est jamais touchée ; un second passage n'écrit rien.
"""
from django.db import migrations

DATASET = 'crm_leads'
ANCIEN = {'formula': 'signes / total * 100', 'aggregates': [
    {'alias': 'signes', 'fn': 'sum', 'field': 'signe_num'},
    {'alias': 'total', 'fn': 'count', 'field': 'id'}]}
NOUVEAU = {'adapter': 'reporting.taux_gain'}
DESCRIPTION = ('Part des pistes gagnées parmi les pistes non perdues (taux de '
               'gain du reporting).')


def realigner(apps, schema_editor):
    Definition = apps.get_model('semantic', 'MetricDefinition')
    Version = apps.get_model('semantic', 'MetricDefinitionVersion')
    for m in Definition.objects.filter(
            cle='taux_conversion', dataset=DATASET).iterator(chunk_size=500):
        if m.mesure != ANCIEN:
            continue
        Definition.objects.filter(pk=m.pk).update(
            dataset='', mesure=dict(NOUVEAU), description=DESCRIPTION)
        dernier = (Version.objects.filter(metric_definition=m)
                   .order_by('-version').values_list('version', flat=True)
                   .first() or 0)
        Version.objects.create(
            company_id=m.company_id, metric_definition=m, version=dernier + 1,
            libelle=m.libelle, dataset='', mesure=dict(NOUVEAU),
            filtres=m.filtres, unite=m.unite)


class Migration(migrations.Migration):

    dependencies = [
        ('semantic', '0005_aana_ca_total_ht'),
    ]

    operations = [
        migrations.RunPython(realigner, migrations.RunPython.noop),
    ]
