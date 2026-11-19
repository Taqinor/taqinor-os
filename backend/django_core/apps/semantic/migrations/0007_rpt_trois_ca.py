"""RPT1 (copilote vague 2) — les trois « CA » de l'ERP portent chacun leur nom.

Un « CA » nu pouvait être répondu de trois façons : encaissé (tableau de bord),
facturé (``ca_ht``) ou signé (devis acceptés). Données seules, patron de 0005 :

* ``ca_signe_ht`` et ``encaisse_ht`` sont CRÉÉES (version 1) pour chaque société
  qui porte déjà ``ca_ht`` — c'est-à-dire qui a semé ses métriques cœur ; une
  société qui n'a rien semé garde un catalogue vide (``seed_metriques`` reste
  le seul chemin pour elle) ;
* ``ca_ht`` / ``ca_ttc`` dont le libellé est EXACTEMENT l'ancien défaut passent
  à « CA facturé HT / TTC » (version dernier + 1). Un libellé retouché par le
  fondateur n'est jamais touché ; un second passage n'écrit rien.
"""
from django.db import migrations

ANCIEN = {
    'ca_ht': ("Chiffre d'affaires HT",
              'Somme des montants HT des factures émises, hors factures '
              'annulées.'),
    'ca_ttc': ("Chiffre d'affaires TTC",
               'Somme des montants TTC des factures émises, hors factures '
               'annulées.'),
}
NOUVEAU = {
    'ca_ht': ('CA facturé HT',
              "Somme des HT nets d'avoirs des factures émises, payées ou en "
              "retard, à la date d'émission, hors brouillons et factures "
              "annulées."),
    'ca_ttc': ('CA facturé TTC',
               "Somme des TTC nets d'avoirs des factures émises, payées ou en "
               "retard, à la date d'émission, hors brouillons et factures "
               "annulées."),
}
CREEES = {
    'ca_signe_ht': ('CA signé HT',
                    'Somme des HT remisés des devis acceptés en vigueur, à la '
                    'date de signature (un devis remplacé par une révision '
                    'acceptée ne compte pas deux fois).',
                    'reporting.ca_signe_ht'),
    'encaisse_ht': ('Encaissé HT',
                    "Part HT des paiements reçus sur les factures émises, "
                    "payées ou en retard de la période (date d'émission) — le "
                    'calcul du tableau de bord Reporting.',
                    'reporting.encaisse_ht'),
}


def _figer(Version, definition, libelle):
    dernier = (Version.objects.filter(metric_definition=definition)
               .order_by('-version').values_list('version', flat=True)
               .first() or 0)
    Version.objects.create(
        company_id=definition.company_id, metric_definition=definition,
        version=dernier + 1, libelle=libelle, dataset=definition.dataset,
        mesure=definition.mesure, filtres=definition.filtres,
        unite=definition.unite)


def poser(apps, schema_editor):
    Definition = apps.get_model('semantic', 'MetricDefinition')
    Version = apps.get_model('semantic', 'MetricDefinitionVersion')
    seedees = list(Definition.objects.filter(cle='ca_ht')
                   .values_list('company_id', flat=True))
    for company_id in seedees:
        for cle, (libelle, description, adaptateur) in CREEES.items():
            if Definition.objects.filter(company_id=company_id,
                                         cle=cle).exists():
                continue
            definition = Definition.objects.create(
                company_id=company_id, cle=cle, libelle=libelle,
                description=description, dataset='',
                mesure={'adapter': adaptateur}, unite='MAD')
            _figer(Version, definition, libelle)
    # Lecture par lots (`.iterator`) ; écriture ligne à ligne par pk (YOPSB4).
    for definition in Definition.objects.filter(
            cle__in=list(ANCIEN)).iterator(chunk_size=500):
        ancien_libelle, ancienne_description = ANCIEN[definition.cle]
        if definition.libelle != ancien_libelle:
            continue
        libelle, description = NOUVEAU[definition.cle]
        if definition.description != ancienne_description:
            description = definition.description
        Definition.objects.filter(pk=definition.pk).update(
            libelle=libelle, description=description)
        _figer(Version, definition, libelle)


class Migration(migrations.Migration):

    dependencies = [
        ('semantic', '0006_taux_conversion_taux_gain'),
    ]

    operations = [
        migrations.RunPython(poser, migrations.RunPython.noop),
    ]
