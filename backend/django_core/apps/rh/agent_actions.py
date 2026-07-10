"""ARC33 — Actions agentiques de l'app RH (pilote auto-découverte, LECTURE seule).

Déclare, via le registre AG1 (:mod:`apps.agent.registry`), les actions RH que
l'agent peut PROPOSER. Ce module ne contient AUCUNE logique d'exécution et
AUCUN nouvel endpoint : il décrit — en métadonnées — des LECTURES qui passent
par les viewsets RH existants, lesquels re-vérifient rôle ET société à
l'exécution (``IsResponsableOrAdmin`` sur la base RH). AUCUNE action
d'écriture ici (pilote lecture/liste minimale, ARC33).

Permissions : la base RH est gardée par un rôle (``IsResponsableOrAdmin``),
pas par un code ERP fin — comme il n'existe pas de code « rh_voir », on suit
le précédent ``ged.docqa.retrieve`` : ``required_permission=None`` (catalogue
ouvert à tout authentifié), l'endpoint restant l'autorité qui re-vérifie le
rôle + la société à l'exécution.

Enregistrement : AUTO-DÉCOUVERT (ARC33) — ``apps/rh/platform.py`` déclare ce
module dans ``agent_actions_module`` ; ``AgentConfig.ready()`` l'importe et
appelle :func:`register_actions` (convention). RIEN dans ``RhConfig.ready()``.
Idempotente : sans danger si appelée plusieurs fois.
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_INTERNAL, register, _REGISTRY


# Action 1 — Lister les dossiers employés (effectifs). Endpoint réel :
# GET /api/django/rh/employes/ (DossierEmployeViewSet, IsResponsableOrAdmin,
# société scopée côté serveur).
LISTER_EMPLOYES = AgentAction(
    key='rh.employes.list',
    label='Lister les employés',
    description=(
        "Liste les dossiers employés de la société (effectifs). Lecture "
        "seule ; l'endpoint RH re-vérifie le rôle (Responsable/Admin) et la "
        "société à l'exécution."
    ),
    endpoint='/api/django/rh/employes/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission=None,
    risk=RISK_INTERNAL,
)


# Action 2 — Lister les demandes de congé (absences). Endpoint réel :
# GET /api/django/rh/demandes-conge/ (DemandeCongeViewSet, société scopée).
LISTER_DEMANDES_CONGE = AgentAction(
    key='rh.demandes_conge.list',
    label='Lister les demandes de congé',
    description=(
        "Liste les demandes de congé/absence de la société (soumises, "
        "validées, refusées). Lecture seule ; l'endpoint RH re-vérifie le "
        "rôle et la société à l'exécution."
    ),
    endpoint='/api/django/rh/demandes-conge/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission=None,
    risk=RISK_INTERNAL,
)


_ACTIONS = (
    LISTER_EMPLOYES,
    LISTER_DEMANDES_CONGE,
)


def register_actions() -> None:
    """Enregistre les actions RH dans le registre AG1 (idempotent).

    Convention ARC33 : appelée par l'auto-découverte
    (``apps.agent.registry.autodiscover_from_platform_manifests``) — jamais
    par ``RhConfig.ready()``.
    """
    for action in _ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
