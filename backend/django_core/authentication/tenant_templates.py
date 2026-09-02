"""SOL10 — Gabarit de tenant « Solaire » : le moment démo.

Un installateur s'inscrit et atterrit dans un ERP DÉJÀ EN FORME SOLAIRE, au
lieu d'un ERP générique qu'il faudrait configurer une demi-journée. C'est le
terrain sur lequel se juge une démo face à Vesta / OpusFlow.

CE MODULE NE CRÉE AUCUN MODÈLE ET AUCUNE DONNÉE INVENTÉE : il COMPOSE
l'existant, dans l'ordre, chaque brique étant déjà livrée et testée ailleurs :

  1. `authentication.module_seeds` (SOL8)   — modules rares éteints ;
  2. `apps.adminops.plan_seeds`   (SOL9)    — plan de licence « Solaire »,
     assigné au `CompanyProfile` de CE tenant ;
  3. `authentication.views._create_system_roles` — rôles types (Directeur,
     Responsable, Commercial, Technicien… le vocabulaire d'un installateur) ;
  4. la STRUCTURE de catalogue solaire (taxonomie de `seed_catalogue`) ;
  5. `apps.reporting.DashboardConfig` — cartes solaires par défaut.

RÈGLE CHECKED-FACTS, ABSOLUE (mémoire fondateur) — LE POINT LE PLUS IMPORTANT
DE CETTE TÂCHE. Le catalogue seedé du dépôt porte des prix RÉELS **en MAD**.
Pour un tenant HORS MAROC, ces prix ne veulent rien dire et il n'existe AUCUNE
source pour des prix EUR : on ne seede donc que la STRUCTURE (les catégories),
JAMAIS un produit prix compris, et surtout jamais un prix converti ou estimé.
L'installateur renseigne ses propres prix — c'est la seule vérité disponible.

Idempotent : ré-appliquer le gabarit ne crée aucun doublon et n'écrase aucune
saisie (get_or_create partout).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PAYS_MAROC = 'MA'

#: SOL10 — cartes du tableau de bord d'un installateur solaire, par palier.
#: Sous-ensemble ORDONNÉ de `apps.reporting.models.ALL_DASHBOARD_CARDS`
#: (jamais une clé inventée : la garde `_cartes_valides` le vérifie).
CARTES_SOLAIRES = {
    # Direction : le pipeline et l'argent d'abord, le stock ensuite.
    'admin': [
        'kpis', 'pipeline', 'conversion', 'ca_mensuel', 'creances',
        'statuts_factures', 'stock_alerte', 'top_produits', 'commercial',
        'kpi_federes', 'integrite',
    ],
    'responsable': [
        'kpis', 'pipeline', 'conversion', 'ca_mensuel', 'creances',
        'statuts_factures', 'stock_alerte', 'commercial',
    ],
    # Terrain / commercial : ce qu'il peut faire avancer aujourd'hui.
    'normal': ['kpis', 'pipeline', 'conversion', 'ca_mensuel'],
}


def _cartes_valides(cartes):
    """Filtre les clés inconnues (jamais une carte inventée au dashboard)."""
    from apps.reporting.models import ALL_DASHBOARD_CARDS
    connues = set(ALL_DASHBOARD_CARDS)
    return [c for c in cartes if c in connues]


def _assigner_plan_solaire(company):
    """Crée/rafraîchit le plan « Solaire » et l'assigne au profil du tenant."""
    from apps.adminops.plan_seeds import seed_plan_solaire
    from apps.parametres.models import CompanyProfile

    plan, _cree = seed_plan_solaire()
    profil, _ = CompanyProfile.objects.get_or_create(
        company=company, defaults={'nom': company.nom})
    if profil.plan_id != plan.pk:
        profil.plan = plan
        profil.save(update_fields=['plan'])
    return plan


def _seed_structure_catalogue(company, *, avec_produits=False):
    """Catégories du catalogue solaire. STRUCTURE SEULE par défaut.

    Renvoie ``{'categories': [...], 'produits': bool}``.

    Le catalogue PRODUIT du dépôt (`seed_catalogue`) porte des prix RÉELS en
    MAD : il n'est posé que sur demande EXPLICITE (`avec_produits=True`) ET
    pour un tenant MAROCAIN. Hors Maroc, on s'arrête à la taxonomie — il
    n'existe aucune source de prix EUR, et un prix converti ou estimé serait
    un chiffre inventé (règle checked-facts, non négociable).
    """
    from apps.stock.management.commands.seed_catalogue import TAXONOMIE
    from apps.stock.models import Categorie

    creees = []
    for nom, ordre in TAXONOMIE:
        _cat, cree = Categorie.objects.get_or_create(
            company=company, nom=nom,
            defaults={'description': 'Catalogue solaire (gabarit SOL10)',
                      'ordre': ordre})
        if cree:
            creees.append(nom)

    pays = (getattr(company, 'pays', PAYS_MAROC) or PAYS_MAROC).upper()
    if not avec_produits or pays != PAYS_MAROC:
        return {'categories': creees, 'produits': False}

    from django.core.management import call_command
    try:
        call_command('seed_catalogue', company_slug=company.slug, verbosity=0)
    except Exception as exc:  # noqa: BLE001 — le gabarit ne casse jamais
        logger.warning(
            'SOL10 : catalogue non seedé pour %s : %s', company.slug, exc)
        return {'categories': creees, 'produits': False}
    return {'categories': creees, 'produits': True}


def _seed_dashboard_solaire(company):
    """Cartes solaires par défaut, une config par palier de rôle."""
    from apps.reporting.models import DashboardConfig

    poses = []
    for palier, cartes in CARTES_SOLAIRES.items():
        valides = _cartes_valides(cartes)
        _cfg, cree = DashboardConfig.objects.get_or_create(
            company=company, user=None, menu_tier=palier,
            defaults={'cards': valides})
        if cree:
            poses.append(palier)
    return poses


def appliquer_gabarit_solaire(company, *, user=None, avec_catalogue_produits=False):
    """Met un tenant NEUF « en forme solaire ». Idempotent, best-effort.

    Appelé sur les DEUX chemins de création (signup public, console founder) :
    léger par défaut (~15 lignes écrites — aucun produit). Le catalogue PRODUIT
    marocain (prix réels en MAD) reste OPT-IN, via
    `manage.py appliquer_gabarit_solaire --avec-catalogue`.

    Renvoie un dict de compte rendu (consommé par la commande de gestion et
    par les tests). Chaque étape est isolée : une brique indisponible ne casse
    jamais les autres ni la création du tenant.
    """
    from .module_seeds import semer_modules_off_par_defaut
    from .views import _create_system_roles

    rapport = {'company': company.slug, 'pays': getattr(company, 'pays', '')}

    etapes = (
        ('modules_eteints', lambda: semer_modules_off_par_defaut(company)),
        ('plan', lambda: _assigner_plan_solaire(company).code),
        ('roles', lambda: sorted(_create_system_roles(company))),
        ('catalogue', lambda: _seed_structure_catalogue(
            company, avec_produits=avec_catalogue_produits)),
        ('dashboard', lambda: _seed_dashboard_solaire(company)),
    )
    for nom, etape in etapes:
        try:
            rapport[nom] = etape()
        except Exception as exc:  # noqa: BLE001 — best-effort, étapes isolées
            logger.warning('SOL10 : étape « %s » KO : %s', nom, exc,
                           exc_info=True)
            rapport[nom] = f'erreur: {exc}'
    return rapport
