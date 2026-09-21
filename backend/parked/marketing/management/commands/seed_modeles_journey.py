"""NTMKT15 — Bibliothèque de modèles de journeys (seed).

Livre 4 gabarits EN GRAPHE (nœuds + arcs NTMKT12) orientés B2B solaire
industriel/agricole, EN PLUS des 5 recettes linéaires XMKT20 (jamais
remplacées) : relance devis étude d'autoconsommation, cycle appel d'offres,
onboarding installateur partenaire, campagne saisonnière (post-Ramadan /
rentrée agricole).

Idempotente et additive : un modèle déjà présent (même nom + même société)
est IGNORÉ, jamais réécrit — un second run est un no-op.

Run:
  docker compose exec django_core python manage.py seed_modeles_journey
  (option --company-slug, défaut : taqinor-demo)
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.marketing.models import ModeleJourney


def _n(cle, type_noeud, libelle, x, y, config=None):
    return {
        'cle': cle, 'type_noeud': type_noeud, 'libelle': libelle,
        'position_x': x, 'position_y': y, 'config': config or {},
    }


def _a(source, cible, condition='toujours', valeur='', ordre=1):
    return {
        'source': source, 'cible': cible, 'condition': condition,
        'valeur': valeur, 'ordre': ordre,
    }


MODELES = [
    {
        'nom': "Relance devis — étude d'autoconsommation",
        'categorie': 'Industriel / Commercial',
        'description': (
            "Relance d'un devis industriel accompagné d'une étude "
            "d'autoconsommation : rappel à J+3, embranchement selon "
            "l'ouverture, appel commercial si silence."),
        'graphe': {
            'noeuds': [
                _n('start', 'declencheur', 'Devis étude envoyé', 20, 20),
                _n('attente', 'attente', 'Attendre 3 jours', 20, 120,
                   {'delai_jours': 3}),
                _n('relance', 'action', 'Email — points clés de l\'étude',
                   220, 120, {'canal': 'email'}),
                _n('appel', 'action', 'Appel — décideur technique', 220, 240,
                   {'canal': 'appel'}),
                _n('fin', 'sortie', 'Fin', 420, 180),
            ],
            'arcs': [
                _a('start', 'attente'),
                _a('attente', 'relance', 'a_ouvert', '', 1),
                _a('attente', 'appel', 'toujours', '', 2),
                _a('relance', 'fin'),
                _a('appel', 'fin'),
            ],
        },
    },
    {
        'nom': "Cycle appel d'offres",
        'categorie': 'Appels d\'offres',
        'description': (
            "Suivi d'un dossier d'appel d'offres : accusé de dépôt, attente "
            "jusqu'au prochain jour ouvré pour la relance, sortie à "
            "l'attribution."),
        'graphe': {
            'noeuds': [
                _n('start', 'declencheur', 'Dossier déposé', 20, 20),
                _n('accuse', 'action', 'Email — accusé de dépôt', 20, 120,
                   {'canal': 'email'}),
                _n('jusqua', 'attente_jusqu_a', 'Prochain lundi 9h', 220, 120,
                   {'mode': 'jour_ouvre', 'heure': 9, 'jour_semaine': 0}),
                _n('suivi', 'action', 'Appel — suivi commission', 420, 120,
                   {'canal': 'appel'}),
                _n('fin', 'sortie', 'Fin', 620, 120),
            ],
            'arcs': [
                _a('start', 'accuse'),
                _a('accuse', 'jusqua'),
                _a('jusqua', 'suivi'),
                _a('suivi', 'fin'),
            ],
        },
    },
    {
        'nom': 'Onboarding installateur partenaire',
        'categorie': 'Partenaires',
        'description': (
            "Accueil d'un installateur partenaire : kit de bienvenue, "
            "documentation technique à J+7, invitation formation pour les "
            "partenaires engagés (score)."),
        'graphe': {
            'noeuds': [
                _n('start', 'declencheur', 'Partenaire signé', 20, 20),
                _n('kit', 'action', 'WhatsApp — kit de bienvenue', 20, 120,
                   {'canal': 'whatsapp'}),
                _n('attente', 'attente', 'Attendre 7 jours', 220, 120,
                   {'delai_jours': 7}),
                _n('doc', 'action', 'Email — documentation technique',
                   420, 60, {'canal': 'email'}),
                _n('formation', 'action', 'Email — invitation formation',
                   420, 200, {'canal': 'email'}),
                _n('fin', 'sortie', 'Fin', 620, 120),
            ],
            'arcs': [
                _a('start', 'kit'),
                _a('kit', 'attente'),
                _a('attente', 'formation', 'score_seuil', '60', 1),
                _a('attente', 'doc', 'toujours', '', 2),
                _a('doc', 'fin'),
                _a('formation', 'fin'),
            ],
        },
    },
    {
        'nom': 'Campagne saisonnière — post-Ramadan / rentrée agricole',
        'categorie': 'Agricole',
        'description': (
            "Réveil saisonnier de la base agricole : offre pompage solaire, "
            "relance des cliqueurs, sortie propre pour les autres."),
        'graphe': {
            'noeuds': [
                _n('start', 'declencheur', 'Ouverture de saison', 20, 20),
                _n('offre', 'action', 'Email — offre pompage solaire', 20, 120,
                   {'canal': 'email'}),
                _n('attente', 'attente', 'Attendre 4 jours', 220, 120,
                   {'delai_jours': 4}),
                _n('chaud', 'action', 'WhatsApp — devis pompage', 420, 60,
                   {'canal': 'whatsapp'}),
                _n('fin', 'sortie', 'Fin', 420, 200),
            ],
            'arcs': [
                _a('start', 'offre'),
                _a('offre', 'attente'),
                _a('attente', 'chaud', 'a_clique', '', 1),
                _a('attente', 'fin', 'toujours', '', 2),
                _a('chaud', 'fin'),
            ],
        },
    },
]


class Command(BaseCommand):
    help = ("NTMKT15 — sème 4 modèles de journeys B2B solaire (graphes "
            "NTMKT12) ; idempotent et additif.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', default='taqinor-demo',
            help="Slug de la société à semer (défaut : taqinor-demo).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options['company_slug']
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CommandError(f"Société de slug '{slug}' introuvable.")

        crees, ignores = [], []
        for modele in MODELES:
            if ModeleJourney.objects.filter(
                    company=company, nom=modele['nom']).exists():
                ignores.append(modele['nom'])
                continue
            ModeleJourney.objects.create(
                company=company,
                nom=modele['nom'],
                categorie=modele['categorie'],
                description=modele['description'],
                graphe=modele['graphe'],
            )
            crees.append(modele['nom'])

        self.stdout.write(self.style.SUCCESS(
            f'Modèles de journey créés : {len(crees)} '
            f'({", ".join(crees) or "aucun"})'))
        self.stdout.write(
            f'Déjà présents (ignorés) : {len(ignores)} '
            f'({", ".join(ignores) or "aucun"})')
