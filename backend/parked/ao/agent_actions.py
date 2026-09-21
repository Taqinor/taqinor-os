"""AOF167 — Actions agentiques du module Appels d'offres (LECTURE SEULE).

Déclare, via le registre AG1 (:mod:`apps.agent.registry`), ce que l'agent
conversationnel peut RÉELLEMENT faire sur le domaine AO. Ce module ne contient
aucune logique d'exécution et n'ouvre AUCUN endpoint neuf : il décrit — en
métadonnées — des LECTURES qui passent par les routes AO existantes, lesquelles
re-vérifient permission ET société à l'exécution (``AoBaseViewSet`` →
``ScopedPermission`` avec ``read_permission = ao_voir``).

Ce que l'agent NE PEUT PAS faire ici, et pourquoi
------------------------------------------------
* **Écrire un montant.** Aucune action ne vise ``bordereaux-prix``,
  ``lignes-bordereau`` ni un champ ``montant_offre_*``. Un agent qui corrige un
  prix unitaire dans un bordereau à prix unitaires modifie l'offre remise à un
  maître d'ouvrage — c'est une décision humaine, définitive et opposable.
* **Déclencher un dépôt.** Aucune action ne vise ``changer-statut``,
  ``publier``, ``retenir`` ni ``dossiers-soumission``. Déposer un pli est un
  acte irréversible avec une date de couperet ; le faire déclencher par une
  conversation serait le pire endroit possible pour une erreur d'intention.
* **Toucher l'économie directeur.** Coût de revient, marge, bénéfice et
  ``prix_achat`` vivent derrière ``ao_rentabilite_voir`` (AOF2), dans des
  endpoints SÉPARÉS que ce module ne mentionne jamais. Une action agentique
  n'est pas un contournement de permission : le catalogue AO ne connaît même
  pas le chemin.

Permissions : toutes les actions déclarent ``required_permission='ao_voir'``
— le code de LECTURE réel du domaine (``apps/ao/permissions.py``), celui-là
même que porte le socle de viewsets. Aucune action ne déclare un code
d'écriture, et aucune ne déclare ``None`` : contrairement à ``compta``, le
domaine AO a un code de lecture, donc l'omettre serait un mensonge par défaut.

Enregistrement : AUTO-DÉCOUVERT (ARC33) — ``apps/ao/platform.py`` déclare ce
module dans ``agent_actions_module`` ; ``AgentConfig.ready()`` l'importe et
appelle :func:`register_actions`. Idempotente.
"""
from __future__ import annotations

from apps.agent.registry import (
    _REGISTRY, RISK_INTERNAL, AgentAction, register,
)

from .permissions import AO_VOIR

__all__ = ['ACTIONS', 'register_actions']

#: Racine de TOUS les endpoints déclarés ici — un test l'impose : une action AO
#: qui pointerait ailleurs sortirait du périmètre que ce module documente.
PREFIXE_ENDPOINT = '/api/django/ao/'

#: Fragments d'endpoint INTERDITS : écriture d'un montant, dépôt, économie.
#: Le test les cherche dans chaque endpoint déclaré — c'est la garde qui
#: survivra à l'ajout d'une action par un futur agent pressé.
FRAGMENTS_INTERDITS = (
    'bordereau', 'ligne', 'changer-statut', 'publier', 'retenir',
    'dossiers-soumission', 'rentabilite', 'economie', 'cout',
)


# Action 1 — Les appels d'offres d'un lead.
# Endpoint réel : GET /api/django/ao/appels-offres/?lead=<id> (le filtre existe,
# ``lead_id`` restant un ENTIER OPAQUE — jamais une FK vers crm.Lead).
LISTER_AO_DU_LEAD = AgentAction(
    key='ao.appels_offres.par_lead',
    label="Lister les appels d'offres d'un lead",
    description=(
        "Liste les appels d'offres rattachés à un lead : référence, objet, "
        "acheteur, statut et date limite de remise des plis. Lecture seule ; "
        "la route AO re-vérifie la permission « ao_voir » et la société à "
        "l'exécution."
    ),
    endpoint='/api/django/ao/appels-offres/?lead={lead_id}',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'lead_id': {'type': 'integer',
                        'description': 'Identifiant du lead CRM'},
        },
        'required': ['lead_id'],
    },
    required_permission=AO_VOIR,
    risk=RISK_INTERNAL,
)

# Action 2 — L'échéance la plus proche (rappels échus, non traités).
# Endpoint réel : GET /api/django/ao/echeances-ao/dues/
ECHEANCES_DUES = AgentAction(
    key='ao.echeances.dues',
    label="Donner les échéances d'appel d'offres dues",
    description=(
        "Liste les dates clés d'appels d'offres dont le rappel est échu et "
        "non traité (remise des plis, ouverture, fin de validité), triées par "
        "date — la plus proche en tête. Un dossier se perd sur une date, "
        "jamais sur la technique. Lecture seule."
    ),
    endpoint='/api/django/ao/echeances-ao/dues/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission=AO_VOIR,
    risk=RISK_INTERNAL,
)

# Action 3 — Capacité DÉMONTRÉE (variantes retenues) vs ENGAGÉE (bâtiments).
# Endpoint réel : GET /api/django/ao/tableau-marches/ (AOF166).
CAPACITE_ET_MARCHES = AgentAction(
    key='ao.tableau_marches.lire',
    label='Restituer la capacité démontrée et le tableau des marchés',
    description=(
        "Rend en un seul appel : les appels d'offres en cours rangés par "
        "échéance de remise, les échéances dues, le taux de réussite CALCULÉ "
        "depuis les résultats d'ouverture des plis, la capacité DÉMONTRÉE "
        "(variantes retenues) face à la capacité ENGAGÉE (bâtiments), les "
        "cautions immobilisées et les marchés en exécution. Aucun coût, "
        "aucune marge : l'économie d'un AO n'est pas dans cette vue."
    ),
    endpoint='/api/django/ao/tableau-marches/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission=AO_VOIR,
    risk=RISK_INTERNAL,
)

# Action 4 — Capacité démontrée D'UN BÂTIMENT, toiture par toiture.
# Endpoint réel : GET /api/django/ao/variantes-calepinage/?toiture=<id> —
# le filtre ``toiture`` existe sur le viewset. LECTURE : ni ``publier`` ni
# ``retenir`` ne sont déclarés ici (ce sont des POST qui engagent un plan).
CAPACITE_DU_BATIMENT = AgentAction(
    key='ao.variantes.par_toiture',
    label="Restituer la capacité démontrée d'une toiture",
    description=(
        "Liste les variantes de calepinage d'une toiture avec leur rôle "
        "(retenue / alternative / sensibilité / marche d'échelle), leur "
        # « écarts », pas « marges » : ce que la preuve porte, c'est la
        # DIFFÉRENCE entre le compte retenu et le compte optimal. Employer
        # « marge » dans le domaine AO fait lire de l'économie directeur là où
        # il n'y en a pas — et le ratchet des mots d'argent le refuse, à raison.
        "compte de modules, leur puissance et leur PREUVE (total retenu vs "
        "total optimal, écarts). Lecture seule : l'agent ne publie ni ne "
        "retient jamais une variante — publier, c'est engager un plan."
    ),
    endpoint='/api/django/ao/variantes-calepinage/?toiture={toiture_id}',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'toiture_id': {'type': 'integer',
                           'description': 'Identifiant de la toiture'},
        },
        'required': ['toiture_id'],
    },
    required_permission=AO_VOIR,
    risk=RISK_INTERNAL,
)

# Action 5 — Contrôle de cohérence du dossier, DANS SA FORME DISPONIBLE.
# Endpoint réel : GET /api/django/ao/appels-offres/{id}/points-a-lever/ (AOF24).
# Le contrôleur de cohérence croisée complet (~14 invariants) appartient à la
# fabrique documentaire et n'existe pas encore : déclarer un contrôle plus
# large que ce qui est câblé serait exactement la dérive qu'ARC41 interdit.
CONTROLE_DE_COHERENCE = AgentAction(
    key='ao.coherence.points_a_lever',
    label='Lancer le contrôle de cohérence du dossier',
    description=(
        "Rend les points « à confirmer à l'exécution » DÉRIVÉS de la donnée : "
        "chaque cote au statut « à confirmer » et chaque obstacle actif non "
        "engageable (lu sur plan, deviné, déclaré par le client), plus la "
        "mention de cartouche opposable du relevé le plus récent. Rien n'est "
        "saisi : ce que l'agent lit est ce que le dossier démontre."
    ),
    endpoint='/api/django/ao/appels-offres/{id}/points-a-lever/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer',
                   'description': "Identifiant de l'appel d'offres"},
        },
        'required': ['id'],
    },
    required_permission=AO_VOIR,
    risk=RISK_INTERNAL,
)


ACTIONS = (
    LISTER_AO_DU_LEAD,
    ECHEANCES_DUES,
    CAPACITE_ET_MARCHES,
    CAPACITE_DU_BATIMENT,
    CONTROLE_DE_COHERENCE,
)


def register_actions() -> None:
    """Enregistre les actions AO dans le registre AG1 (idempotent).

    Convention ARC33 : appelée par l'auto-découverte
    (``apps.agent.registry.autodiscover_from_platform_manifests``) — jamais
    par ``AoConfig.ready()``.
    """
    for action in ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
