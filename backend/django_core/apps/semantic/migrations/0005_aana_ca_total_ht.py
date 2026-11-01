"""AANA77 — `ca_ht` / `ca_ttc` / `panier_moyen` lisent `Facture.total_ht` /
`total_ttc` (adaptateurs `reporting.*`, D-AANA-6) au lieu des colonnes
`montant_ht` / `montant_ttc`, NULL sur toute facture classique.

Données seules : une définition dont la mesure est EXACTEMENT l'ancien défaut
de `seed_metriques` (dataset `ventes_factures`) passe sur l'adaptateur, avec
une version figée (dernier + 1, jamais `count()+1`). Ses filtres sont gardés
(l'adaptateur les applique). Une mesure retouchée n'est jamais touchée ; un
second passage n'écrit rien.
"""
from django.db import migrations

DATASET = 'ventes_factures'
ANCIEN = {
    'ca_ht': {'field': 'montant_ht', 'agg': 'sum'},
    'ca_ttc': {'field': 'montant_ttc', 'agg': 'sum'},
    'panier_moyen': {
        'formula': 'ca / nb',
        'aggregates': [
            {'alias': 'ca', 'fn': 'sum', 'field': 'montant_ttc'},
            {'alias': 'nb', 'fn': 'count', 'field': 'id'},
        ],
    },
}
NOUVEAU = {cle: {'adapter': 'reporting.%s' % cle} for cle in ANCIEN}


def realigner(apps, schema_editor):
    Definition = apps.get_model('semantic', 'MetricDefinition')
    Version = apps.get_model('semantic', 'MetricDefinitionVersion')
    # Lecture par lots (`.iterator`) ; écriture ligne à ligne par pk (YOPSB4).
    for m in Definition.objects.filter(
            cle__in=list(ANCIEN), dataset=DATASET).iterator(chunk_size=500):
        if m.mesure != ANCIEN[m.cle]:
            continue
        m.dataset, m.mesure = '', dict(NOUVEAU[m.cle])
        dims = [] if m.dimensions_par_defaut == ['mois_emission'] else \
            m.dimensions_par_defaut
        Definition.objects.filter(pk=m.pk).update(
            dataset=m.dataset, mesure=m.mesure, dimensions_par_defaut=dims)
        dernier = (Version.objects.filter(metric_definition=m)
                   .order_by('-version').values_list('version', flat=True)
                   .first() or 0)
        Version.objects.create(
            company_id=m.company_id, metric_definition=m, version=dernier + 1,
            libelle=m.libelle, dataset=m.dataset, mesure=m.mesure,
            filtres=m.filtres, unite=m.unite)


class Migration(migrations.Migration):

    dependencies = [
        ('semantic', '0004_aana_ca_sans_brouillon'),
    ]

    operations = [
        migrations.RunPython(realigner, migrations.RunPython.noop),
    ]
