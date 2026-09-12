"""NTDATA11 — `seed_metriques` : les 8 métriques CŒUR, par société.

IDEMPOTENTE ET ADDITIVE, au sens strict du dépôt (même contrat que
`seed_catalogue`) : la commande CRÉE une métrique dont la clé manque, et NE
TOUCHE JAMAIS une métrique existante — ni sa mesure, ni son libellé, ni ses
filtres, ni son unité. Le fondateur peut donc corriger une définition sans
qu'un déploiement ultérieur la réécrase. Deux exécutions consécutives laissent
exactement les mêmes 8 métriques, aux mêmes valeurs.

LES HUIT, ET D'OÙ VIENT CHAQUE CHIFFRE
--------------------------------------
Aucune de ces définitions n'invente un nombre : chacune pointe soit un champ
RÉELLEMENT stocké, soit le calcul qui fait déjà autorité dans le dépôt.

* `ca_ht` / `ca_ttc` — somme de `Facture.montant_ht` / `montant_ttc`
  (colonnes du modèle), factures annulées exclues.
* `panier_moyen` — CA TTC / nombre de factures, sur la même population.
* `taux_conversion` — somme(`signe_num`) / nombre de leads × 100, où
  `signe_num` est l'indicateur 1/0 « étape SIGNED ET non perdu » du dataset
  `crm_leads` : EXACTEMENT la règle de `crm.selectors`.
* `mrr` — valeur annuelle des contrats de maintenance ACTIFS ÷ 12
  (`sav_contrats.valeur_annuelle`, dérivée du prix de période × 12/mois).
* `marge_brute` et `dso` — ADAPTATEURS `compta.*` : lus du cockpit
  `pilotage_financier` (grand livre). Les recalculer en SQL créerait un
  second chiffre.
* `valeur_pipeline_ponderee` — ADAPTATEUR `crm.pipeline_pondere` : réutilise
  les scorers `_lead_forecast_value` × `_lead_win_weight` de l'écran Pipeline.

Une métrique dont l'adaptateur n'est pas enregistré (module désactivé) est
quand même SEMÉE : elle reste une définition inerte jusqu'à ce que son module
revienne, et le résolveur dit alors clairement ce qui manque.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.semantic.models import MetricDefinition
from authentication.models import Company

#: Les 8 métriques cœur. `cle` est la clé d'idempotence (unique par société).
METRIQUES_COEUR = [
    {
        'cle': 'ca_ht',
        'libelle': "Chiffre d'affaires HT",
        'description': "Somme des montants HT des factures émises, hors "
                       'factures annulées.',
        'dataset': 'ventes_factures',
        'mesure': {'field': 'montant_ht', 'agg': 'sum'},
        'filtres': {'statut__in': ['brouillon', 'emise', 'payee',
                                   'en_retard']},
        'unite': MetricDefinition.Unite.MAD,
        'dimensions_par_defaut': ['mois_emission'],
    },
    {
        'cle': 'ca_ttc',
        'libelle': "Chiffre d'affaires TTC",
        'description': 'Somme des montants TTC des factures émises, hors '
                       'factures annulées.',
        'dataset': 'ventes_factures',
        'mesure': {'field': 'montant_ttc', 'agg': 'sum'},
        'filtres': {'statut__in': ['brouillon', 'emise', 'payee',
                                   'en_retard']},
        'unite': MetricDefinition.Unite.MAD,
        'dimensions_par_defaut': ['mois_emission'],
    },
    {
        'cle': 'panier_moyen',
        'libelle': 'Panier moyen',
        'description': 'Chiffre d\'affaires TTC divisé par le nombre de '
                       'factures de la période.',
        'dataset': 'ventes_factures',
        'mesure': {
            'formula': 'ca / nb',
            'aggregates': [
                {'alias': 'ca', 'fn': 'sum', 'field': 'montant_ttc'},
                {'alias': 'nb', 'fn': 'count', 'field': 'id'},
            ],
        },
        'filtres': {'statut__in': ['brouillon', 'emise', 'payee',
                                   'en_retard']},
        'unite': MetricDefinition.Unite.MAD,
    },
    {
        'cle': 'taux_conversion',
        'libelle': 'Taux de conversion',
        'description': 'Part des pistes signées (étape Signé, non perdues) '
                       'dans le total des pistes.',
        'dataset': 'crm_leads',
        'mesure': {
            'formula': 'signes / total * 100',
            'aggregates': [
                {'alias': 'signes', 'fn': 'sum', 'field': 'signe_num'},
                {'alias': 'total', 'fn': 'count', 'field': 'id'},
            ],
        },
        'unite': MetricDefinition.Unite.POURCENT,
        'format': 1,
    },
    {
        'cle': 'mrr',
        'libelle': 'Revenu récurrent mensuel (MRR)',
        'description': 'Valeur annuelle des contrats de maintenance actifs, '
                       'ramenée au mois.',
        'dataset': 'sav_contrats',
        'mesure': {
            'formula': 'annuel / 12',
            'aggregates': [
                {'alias': 'annuel', 'fn': 'sum', 'field': 'valeur_annuelle'},
            ],
        },
        'filtres': {'actif': True},
        'unite': MetricDefinition.Unite.MAD,
    },
    {
        'cle': 'marge_brute',
        'libelle': 'Marge brute',
        'description': 'Produits moins charges de la période, lus du grand '
                       'livre (cockpit Pilotage financier).',
        'dataset': '',
        'mesure': {'adapter': 'compta.marge_brute'},
        'unite': MetricDefinition.Unite.MAD,
    },
    {
        'cle': 'dso',
        'libelle': 'DSO (délai moyen de règlement)',
        'description': 'Encours clients rapporté au chiffre d\'affaires de la '
                       'période, en jours — lu du grand livre.',
        'dataset': '',
        'mesure': {'adapter': 'compta.dso'},
        'unite': MetricDefinition.Unite.JOURS,
        'format': 0,
    },
    {
        'cle': 'valeur_pipeline_ponderee',
        'libelle': 'Pipeline pondéré',
        'description': 'Valeur prévisionnelle des pistes ouvertes, pondérée '
                       'par leur probabilité de gain.',
        'dataset': '',
        'mesure': {'adapter': 'crm.pipeline_pondere'},
        'unite': MetricDefinition.Unite.MAD,
    },
]


class Command(BaseCommand):
    help = ("Sème les métriques cœur de la couche sémantique (idempotent, "
            "additif : ne modifie JAMAIS une métrique existante).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='Identifiant d\'une société précise (défaut : toutes).')

    def handle(self, *args, **options):
        societes = Company.objects.all()
        if options.get('company'):
            societes = societes.filter(pk=options['company'])
        total_creees = 0
        total_intactes = 0
        for company in societes:
            creees, intactes = self._semer(company)
            total_creees += creees
            total_intactes += intactes
            self.stdout.write(
                '%s : %d métrique(s) créée(s), %d laissée(s) intacte(s).'
                % (company.nom, creees, intactes))
        self.stdout.write(self.style.SUCCESS(
            'seed_metriques : %d créée(s), %d intacte(s) sur %d société(s).'
            % (total_creees, total_intactes, societes.count())))

    @transaction.atomic
    def _semer(self, company):
        existantes = set(
            MetricDefinition.objects
            .filter(company=company)
            .values_list('cle', flat=True))
        creees = 0
        for spec in METRIQUES_COEUR:
            if spec['cle'] in existantes:
                # ADDITIF : une définition déjà là — éditée ou non par le
                # fondateur — n'est JAMAIS réécrite.
                continue
            MetricDefinition.objects.create(company=company, **spec)
            creees += 1
        return creees, len(METRIQUES_COEUR) - creees
