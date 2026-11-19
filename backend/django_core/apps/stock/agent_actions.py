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

from core.champs_stricts import QUANTITE_MAX

from apps.agent.registry import (
    AgentAction, RISK_INTERNAL, RISK_OUTWARD, register, _REGISTRY)


#: REP1 (copilote vague 2, B-1) — valeurs EXACTES de
#: ``MouvementStock.TypeMouvement`` (apps/stock/models.py) que l'assistant peut
#: poser. ``transfert`` / ``rebut`` sont refusés par la route générique
#: (``MouvementStockViewSet.TYPES_REFUSES``) ; ``ajustement`` est accepté par
#: la route mais veut dire NIVEAU VISÉ (le stock DEVIENT la quantité,
#: ``perform_create``) : « ajoute 5 » envoyé en ajustement mettait le stock À 5.
#: Il reste un geste de l'écran Stock, jamais une entrée de l'assistant.
TYPES_MOUVEMENT_ASSISTANT = ('entree', 'sortie')


# Action 1 — une ENTRÉE ou une SORTIE de stock. Endpoint réel : POST
# /api/django/stock/mouvements/ (MouvementStockViewSet). Garde de la route à la
# création : ``HasPermissionOrLegacy('stock_mouvement')`` (``get_permissions``).
# Registre append-only (une erreur se corrige par un mouvement inverse) : une
# quantité de stock change → proposition À CONFIRMER (REP1), plus jamais une
# exécution au vol. La société est forcée côté serveur.
AJUSTER_STOCK = AgentAction(
    key='stock.mouvement.create',
    label='Entrée ou sortie de stock',
    description=(
        "Sert à : poser une entrée (réception, retour) ou une sortie "
        "(consommation, chantier) d'une quantité entière d'un produit, après "
        "confirmation. Ne pas utiliser pour : corriger un niveau d'inventaire "
        "(un ajustement fixe le stock À une valeur : écran Stock), un "
        "transfert ni un rebut. Exemple : « sors 12 panneaux pour le "
        "chantier » → produit, type_mouvement=sortie, quantite=12. Résultat : "
        "le mouvement et le stock avant/après ; 409 si le stock est "
        "insuffisant ou en quarantaine."
    ),
    endpoint='/api/django/stock/mouvements/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'produit': {'type': 'integer', 'title': 'Produit (id)'},
            'type_mouvement': {
                'type': 'string',
                'title': 'Sens',
                'enum': list(TYPES_MOUVEMENT_ASSISTANT),
                'description': ("entree = AJOUTE la quantité au stock ; "
                                "sortie = la RETIRE."),
            },
            'quantite': {
                'type': 'integer', 'title': 'Quantité',
                'minimum': 1, 'maximum': QUANTITE_MAX,
                'description': 'Nombre entier d\'unités déplacées (au moins 1).',
            },
            'reference': {'type': 'string', 'title': 'Référence'},
            'note': {'type': 'string', 'title': 'Note'},
        },
        'required': ['produit', 'type_mouvement', 'quantite'],
    },
    required_permission='stock_mouvement',
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Poser un mouvement de stock : une entrée AJOUTE la quantité au "
        "stock, une sortie la RETIRE (rien n'est fixé à une valeur)."),
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
