"""ARC33 — Actions agentiques de l'app Contrats (pilote auto-découverte,
LECTURE seule).

Déclare, via le registre AG1 (:mod:`apps.agent.registry`), les actions
Contrats que l'agent peut PROPOSER. Ce module ne contient AUCUNE logique
d'exécution et AUCUN nouvel endpoint : il décrit — en métadonnées — des
LECTURES qui passent par le ``ContratViewSet`` existant, lequel re-vérifie
permission ET société à l'exécution (y compris le niveau de confidentialité
par contrat — public/interne/confidentiel — appliqué côté queryset). AUCUNE
action d'écriture ici (pilote lecture/liste minimale, ARC33).

Permissions : le code ERP fin ``contrat_voir`` existe (gardé
``HasPermissionOrLegacy`` côté viewset) — on l'adosse directement.

Enregistrement : AUTO-DÉCOUVERT (ARC33) — ``apps/contrats/platform.py``
déclare ce module dans ``agent_actions_module`` ; ``AgentConfig.ready()``
l'importe et appelle :func:`register_actions` (convention). RIEN dans
``ContratsConfig.ready()``. Idempotente : sans danger si appelée plusieurs
fois.
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_INTERNAL, register, _REGISTRY


# Action 1 — Lister les contrats (CLM). Endpoint réel :
# GET /api/django/contrats/contrats/ (ContratViewSet, société scopée +
# confidentialité par contrat appliquées côté serveur).
LISTER_CONTRATS = AgentAction(
    key='contrats.contrat.list',
    label='Lister les contrats',
    description=(
        "Liste les contrats de la société (cycle de vie contractuel : type, "
        "statut, dates, montant). Lecture seule ; l'endpoint re-vérifie la "
        "permission « contrat_voir », la société et le niveau de "
        "confidentialité de chaque contrat à l'exécution."
    ),
    endpoint='/api/django/contrats/contrats/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission='contrat_voir',
    risk=RISK_INTERNAL,
)


_ACTIONS = (
    LISTER_CONTRATS,
)


def register_actions() -> None:
    """Enregistre les actions Contrats dans le registre AG1 (idempotent).

    Convention ARC33 : appelée par l'auto-découverte
    (``apps.agent.registry.autodiscover_from_platform_manifests``) — jamais
    par ``ContratsConfig.ready()``.
    """
    for action in _ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
