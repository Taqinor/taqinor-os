"""NTDATA11 — `seed_metriques` : les métriques CŒUR, par société.

IDEMPOTENTE ET ADDITIVE, au sens strict du dépôt (même contrat que
`seed_catalogue`) : la commande CRÉE une métrique dont la clé manque, et NE
TOUCHE JAMAIS une métrique existante — ni sa mesure, ni son libellé, ni ses
filtres, ni son unité. Le fondateur peut donc corriger une définition sans
qu'un déploiement ultérieur la réécrase. Deux exécutions consécutives laissent
exactement les mêmes métriques, aux mêmes valeurs.

LES HUIT, ET D'OÙ VIENT CHAQUE CHIFFRE
--------------------------------------
Aucune de ces définitions n'invente un nombre : chacune pointe soit un champ
RÉELLEMENT stocké, soit le calcul qui fait déjà autorité dans le dépôt.

* `ca_ht` / `ca_ttc` / `panier_moyen` — ADAPTATEURS `reporting.*`
  (AANA77, D-AANA-6) : somme de `Facture.total_ht` / `total_ttc` (propriétés
  du noyau canonique, pas des colonnes : `montant_ht`/`montant_ttc` ne sont
  remplis que sur les factures d'échéancier) des factures émises, payées, en
  retard ; panier = CA TTC / nombre de factures.
* `ca_signe_ht` / `encaisse_ht` — ADAPTATEURS `reporting.*` (RPT1) : les deux
  autres « CA » de l'ERP. SIGNÉ = HT remisé des devis acceptés en vigueur,
  daté de la signature ; ENCAISSÉ = part HT des paiements reçus, comme le
  tableau de bord. Les libellés (« CA signé HT », « CA facturé HT »,
  « Encaissé HT ») disent lequel est lequel : jamais un « CA » nu.
* `taux_conversion` — ADAPTATEUR `reporting.taux_gain` (ASOC72, D-AANA-1) :
  LE taux de gain du reporting, leads gagnés ÷ leads NON perdus.
* `mrr` — valeur annuelle des contrats de maintenance ACTIFS ÷ 12
  (`sav_contrats.valeur_annuelle`, dérivée du prix de période × 12/mois).
* `marge_brute` et `dso` NE SONT PLUS SEMÉES (RPT2) : leurs adaptateurs
  `compta.*` n'existent plus (l'app `compta` est parquée) et une métrique
  listée qui ne se résout pas ment à l'assistant. Aucune formule de
  remplacement n'est inventée : le jour où un calcul canonique existe, la clé
  revient avec son adaptateur. Les lignes déjà semées sont désactivées par la
  migration 0008.
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

#: Les métriques cœur. `cle` est la clé d'idempotence (unique par société).
METRIQUES_COEUR = [
    {
        'cle': 'ca_ht',
        'libelle': 'CA facturé HT',
        'description': "Somme des HT nets d'avoirs des factures émises, "
                       "payées ou en retard, à la date d'émission, hors "
                       'brouillons et factures annulées.',
        'dataset': '',
        'mesure': {'adapter': 'reporting.ca_ht'},
        'filtres': {'statut__in': ['emise', 'payee', 'en_retard']},
        'unite': MetricDefinition.Unite.MAD,
    },
    {
        'cle': 'ca_ttc',
        'libelle': 'CA facturé TTC',
        'description': "Somme des TTC nets d'avoirs des factures émises, "
                       "payées ou en retard, à la date d'émission, hors "
                       'brouillons et factures annulées.',
        'dataset': '',
        'mesure': {'adapter': 'reporting.ca_ttc'},
        'filtres': {'statut__in': ['emise', 'payee', 'en_retard']},
        'unite': MetricDefinition.Unite.MAD,
    },
    {
        'cle': 'ca_signe_ht',
        'libelle': 'CA signé HT',
        'description': "Somme des HT remisés des devis acceptés en vigueur, "
                       'à la date de signature (un devis remplacé par une '
                       'révision acceptée ne compte pas deux fois).',
        'dataset': '',
        'mesure': {'adapter': 'reporting.ca_signe_ht'},
        'unite': MetricDefinition.Unite.MAD,
    },
    {
        'cle': 'encaisse_ht',
        'libelle': 'Encaissé HT',
        'description': 'Part HT des paiements reçus sur les factures émises, '
                       "payées ou en retard de la période (date d'émission) "
                       '— le calcul du tableau de bord Reporting.',
        'dataset': '',
        'mesure': {'adapter': 'reporting.encaisse_ht'},
        'unite': MetricDefinition.Unite.MAD,
    },
    {
        'cle': 'panier_moyen',
        'libelle': 'Panier moyen',
        'description': 'Chiffre d\'affaires TTC divisé par le nombre de '
                       'factures de la période.',
        'dataset': '',
        'mesure': {'adapter': 'reporting.panier_moyen'},
        'filtres': {'statut__in': ['emise', 'payee', 'en_retard']},
        'unite': MetricDefinition.Unite.MAD,
    },
    {
        'cle': 'taux_conversion',
        'libelle': 'Taux de conversion',
        'description': 'Part des pistes gagnées parmi les pistes non '
                       'perdues (taux de gain du reporting).',
        'dataset': '',
        'mesure': {'adapter': 'reporting.taux_gain'},
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
