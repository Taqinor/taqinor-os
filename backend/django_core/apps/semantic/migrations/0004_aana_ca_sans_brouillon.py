"""AANA61 — les métriques cœur CA ne comptent plus les factures brouillon.

Données seules : une définition `ca_ht` / `ca_ttc` / `panier_moyen` dont les
filtres sont EXACTEMENT l'ancien défaut de `seed_metriques` est réalignée sur
émise / payée / en retard, avec une version figée (dernier + 1, jamais
`count()+1`). Une définition retouchée par le fondateur n'est jamais touchée ;
un second passage n'écrit rien (les filtres ne sont plus l'ancien défaut).
"""
from django.db import migrations

CLES = ('ca_ht', 'ca_ttc', 'panier_moyen')
ANCIEN = {'statut__in': ['brouillon', 'emise', 'payee', 'en_retard']}
NOUVEAU = {'statut__in': ['emise', 'payee', 'en_retard']}


def realigner(apps, schema_editor):
    Definition = apps.get_model('semantic', 'MetricDefinition')
    Version = apps.get_model('semantic', 'MetricDefinitionVersion')
    for m in Definition.objects.filter(cle__in=CLES, filtres=ANCIEN):
        m.filtres = dict(NOUVEAU)
        Definition.objects.filter(pk=m.pk).update(filtres=m.filtres)
        dernier = (Version.objects.filter(metric_definition=m)
                   .order_by('-version').values_list('version', flat=True)
                   .first() or 0)
        Version.objects.create(
            company_id=m.company_id, metric_definition=m, version=dernier + 1,
            libelle=m.libelle, dataset=m.dataset, mesure=m.mesure,
            filtres=m.filtres, unite=m.unite)


class Migration(migrations.Migration):

    dependencies = [
        ('semantic', '0003_ntdata9_metricdefinitionversion'),
    ]

    operations = [
        migrations.RunPython(realigner, migrations.RunPython.noop),
    ]
