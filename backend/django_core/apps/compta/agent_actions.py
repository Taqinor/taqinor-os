"""ARC33 — Actions agentiques de l'app Compta (pilote auto-découverte,
LECTURE seule).

Déclare, via le registre AG1 (:mod:`apps.agent.registry`), les actions Compta
que l'agent peut PROPOSER. Ce module ne contient AUCUNE logique d'exécution et
AUCUN nouvel endpoint : il décrit — en métadonnées — des LECTURES qui passent
par les viewsets Compta existants, lesquels re-vérifient rôle ET société à
l'exécution (``IsResponsableOrAdmin`` sur la base compta). AUCUNE action
d'écriture ici (pilote lecture/liste minimale, ARC33 — jamais de saisie/
validation/clôture comptable par l'agent dans ce périmètre).

Permissions : les codes ERP compta existants (``compta_saisir``,
``compta_valider``, ``compta_cloturer``) sont des codes d'ÉCRITURE — les
adosser à une lecture serait faux. Comme il n'existe pas de code
« compta_voir », on suit le précédent ``ged.docqa.retrieve`` :
``required_permission=None`` (catalogue ouvert à tout authentifié),
l'endpoint restant l'autorité qui re-vérifie le rôle + la société.

Enregistrement : AUTO-DÉCOUVERT (ARC33) — ``apps/compta/platform.py`` déclare
ce module dans ``agent_actions_module`` ; ``AgentConfig.ready()`` l'importe et
appelle :func:`register_actions` (convention). RIEN dans ``ComptaConfig.
ready()``. Idempotente : sans danger si appelée plusieurs fois.
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_INTERNAL, register, _REGISTRY


# Action 1 — Lister les effets (chèques/traites) et leurs échéances.
# Endpoint réel : GET /api/django/compta/effets/ (EffetViewSet, société
# scopée côté serveur). C'est le calendrier d'échéances de trésorerie.
LISTER_EFFETS = AgentAction(
    key='compta.effets.list',
    label='Lister les effets (échéances)',
    description=(
        "Liste les effets de commerce de la société (chèques, traites/LCN) "
        "avec montant, date d'échéance, banque et statut — le calendrier "
        "d'échéances de trésorerie. Lecture seule ; l'endpoint compta "
        "re-vérifie le rôle (Responsable/Admin) et la société à l'exécution."
    ),
    endpoint='/api/django/compta/effets/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission=None,
    risk=RISK_INTERNAL,
)


_ACTIONS = (
    LISTER_EFFETS,
)


def register_actions() -> None:
    """Enregistre les actions Compta dans le registre AG1 (idempotent).

    Convention ARC33 : appelée par l'auto-découverte
    (``apps.agent.registry.autodiscover_from_platform_manifests``) — jamais
    par ``ComptaConfig.ready()``.
    """
    for action in _ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
