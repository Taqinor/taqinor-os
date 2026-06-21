"""AG7 — Actions agentiques de l'app Stock (catalogue déclaré en code).

Déclare, via le registre AG1 (:mod:`apps.agent.registry`), les actions Stock
que l'agent (relais FastAPI + JWT utilisateur) peut PROPOSER. Ce module ne
contient AUCUNE logique d'exécution et AUCUN nouvel endpoint : il ne fait que
décrire — en métadonnées — des écritures qui passent par les viewsets Stock
existants, qui re-vérifient permission ET société à l'exécution.

Multi-tenant : ``company`` n'apparaît JAMAIS dans le schéma ``inputs`` — la
société est forcée côté serveur par le viewset (``perform_create``) à partir de
``request.user.company`` ; elle ne doit jamais provenir du corps de la requête.

Enregistrement : :func:`register_stock_actions` est appelée depuis
``StockConfig.ready()`` (import différé pour éviter les effets de bord à
l'import). Idempotente : sans danger si ``ready()`` est invoquée plusieurs fois.
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_INTERNAL, register, _REGISTRY


# Action 1 — Ajuster le stock = poster un mouvement de stock (ENTREE/SORTIE/…).
# Endpoint réel : POST /api/django/stock/mouvements/ (MouvementStockViewSet).
# Permission requise par ce viewset à la création : HasPermissionOrLegacy(
# 'stock_mouvement') → code ERP « stock_mouvement ». La société est forcée
# côté serveur (perform_create utilise produit.company / request.user.company).
AJUSTER_STOCK = AgentAction(
    key='stock.mouvement.create',
    label='Ajuster le stock',
    description=(
        "Poste un mouvement de stock (entrée, sortie ou ajustement) sur un "
        "produit. Le serveur calcule quantité_avant/quantité_après, applique "
        "le verrou de ligne produit et force la société du caller."
    ),
    endpoint='/api/django/stock/mouvements/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'produit': {'type': 'integer'},
            'type_mouvement': {
                'type': 'string',
                'description': 'ENTREE | SORTIE | AJUSTEMENT (selon le modèle).',
            },
            'quantite': {'type': 'number'},
            'reference': {'type': 'string'},
            'note': {'type': 'string'},
        },
        'required': ['produit', 'type_mouvement', 'quantite'],
    },
    required_permission='stock_mouvement',
    risk=RISK_INTERNAL,
)


# Action 2 — Créer un brouillon de bon de commande fournisseur (achat).
# Endpoint réel : POST /api/django/stock/bons-commande-fournisseur/
# (BonCommandeFournisseurViewSet) — le BC naît en statut BROUILLON ; il faut
# l'action `envoyer` pour le passer ENVOYE (donc « brouillon » par défaut).
# Permission : le viewset exige IsResponsableOrAdmin à la création — un gardien
# basé sur le RÔLE, pas un code de permission ERP. Comme le filtre catalogue
# AG1 (for_user) ne sait raisonner que sur des codes ERP, on adosse cette
# action au code « stock_creer » (porté par Responsable/Admin/Directeur), qui
# est le pendant ERP le plus proche de IsResponsableOrAdmin pour les achats. Le
# viewset reste l'autorité finale (il re-vérifie le rôle + la société).
BROUILLON_COMMANDE_FOURNISSEUR = AgentAction(
    key='stock.bon_commande_fournisseur.create',
    label='Créer un brouillon de bon de commande fournisseur',
    description=(
        "Crée un bon de commande fournisseur (achat) en statut BROUILLON. La "
        "référence numérotée (préfixe BCF) et la société sont attribuées côté "
        "serveur ; les prix d'achat restent internes."
    ),
    endpoint='/api/django/stock/bons-commande-fournisseur/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'fournisseur': {'type': 'integer'},
            'date_commande': {'type': 'string', 'format': 'date'},
            'note': {'type': 'string'},
            'lignes': {'type': 'array', 'items': {'type': 'object'}},
        },
        'required': ['fournisseur', 'lignes'],
    },
    required_permission='stock_creer',
    risk=RISK_INTERNAL,
)


_ACTIONS = (AJUSTER_STOCK, BROUILLON_COMMANDE_FOURNISSEUR)


def register_stock_actions() -> None:
    """Enregistre les actions Stock dans le registre AG1 (idempotent).

    Sûre si ``StockConfig.ready()`` est appelée plus d'une fois : on ne
    ré-enregistre pas une clé déjà présente.
    """
    for action in _ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
