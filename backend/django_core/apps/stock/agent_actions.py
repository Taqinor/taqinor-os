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

from apps.agent.registry import AgentAction, RISK_OUTWARD, register, _REGISTRY


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
    # Vague 2 — l'aperçu NOMME le produit (`selectors_libelles.libelles_stock`).
    objets={'produit': 'produit'},
)


#: REP2 — UNE ligne de BCF telle que l'assistant peut l'écrire
#: (``LigneBonCommandeFournisseurSerializer``) : produit OU désignation libre,
#: quantité entière > 0. JAMAIS un prix (``prix_achat_unitaire``,
#: ``prix_achat_unitaire_devise``, ``frais_annexes``) : la ligne naît à 0
#: (défaut du modèle ``achats.LigneBonCommandeFournisseur``), l'acheteur règle
#: les prix à l'écran avant l'envoi.
_LIGNE_BCF = {
    'type': 'object',
    'properties': {
        'produit': {'type': 'integer',
                    'description': 'Produit du catalogue (id).'},
        'designation': {'type': 'string',
                        'description': 'Désignation libre si pas de produit.'},
        'quantite': {'type': 'integer', 'minimum': 1},
    },
    'required': ['quantite'],
    'additionalProperties': False,
}


# Action 2 — Créer un brouillon de bon de commande fournisseur (achat).
# Endpoint réel : POST /api/django/stock/bons-commande-fournisseur/
# (BonCommandeFournisseurViewSet) — le BC naît en statut BROUILLON ; il faut
# l'action `envoyer` (geste de l'écran) pour le passer ENVOYE. REP2 — garde
# RÉELLE de la route à la création : ``HasPermissionOrLegacy(
# 'achats_commander')`` (``COMMANDER_ACTIONS``, ASTK17) — l'ancien code
# « stock_creer » montrait l'outil au Commercial responsable (403) et le
# cachait à l'Administrateur (accepté). Proposition À CONFIRMER : une commande
# engage la société même en brouillon.
BROUILLON_COMMANDE_FOURNISSEUR = AgentAction(
    key='stock.bon_commande_fournisseur.create',
    label='Créer un brouillon de bon de commande fournisseur',
    description=(
        "Sert à : préparer un bon de commande fournisseur BROUILLON "
        "(fournisseur, produits et quantités), après confirmation ; rien "
        "n'est envoyé au fournisseur. Ne pas utiliser pour : les manques "
        "d'un chantier (installations.chantier.commander_besoin), fixer un "
        "prix ni envoyer la commande. Exemple : « commande 20 panneaux chez "
        "le fournisseur 3 » → fournisseur=3, lignes=[{produit, "
        "quantite=20}]. Résultat : le BCF brouillon numéroté ; les prix "
        "naissent à 0 et se règlent à l'écran avant l'envoi."
    ),
    endpoint='/api/django/stock/bons-commande-fournisseur/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'fournisseur': {'type': 'integer', 'title': 'Fournisseur (id)'},
            'date_commande': {'type': 'string', 'format': 'date',
                              'title': 'Date de commande'},
            'note': {'type': 'string', 'title': 'Note'},
            'lignes': {'type': 'array', 'title': 'Lignes',
                       'minItems': 1, 'items': _LIGNE_BCF},
        },
        'required': ['fournisseur', 'lignes'],
    },
    required_permission='achats_commander',
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Créer un bon de commande fournisseur BROUILLON (rien n'est envoyé ; "
        "les prix se règlent à l'écran)."),
    objets={'fournisseur': 'fournisseur'},
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
