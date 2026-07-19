"""PUB99 — Actions d'agent (ARC33) du moteur publicitaire — LECTURE SEULE.

Le chatbot (agent SQL/registre) répond à des questions de LECTURE sur le compte
pub via ces actions ; chacune pointe un endpoint DRF EXISTANT qui re-vérifie la
permission + le scope société. Toutes sont ``RISK_INTERNAL`` (lecture) : AUCUNE
action d'écriture n'est exposée au chatbot — proposer/approuver une dépense reste
une décision fondateur GATED, hors scope ici.

Découvert automatiquement par ``apps.agent`` via le
``platform.PLATFORM['agent_actions_module']`` (appelle ``register_actions()``).
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_INTERNAL, _REGISTRY, register

DEPENSE_SEMAINE = AgentAction(
    key='adsengine.spend.week',
    label='Dépense publicitaire de la semaine',
    description=(
        "Combien a-t-on dépensé en publicité cette semaine ? Renvoie les KPIs "
        "du tableau de bord pub (dépense, leads, conversations)."),
    endpoint='/api/django/adsengine/metrics/dashboard/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission='adsengine_view',
    risk=RISK_INTERNAL,
)

TOP_ADS = AgentAction(
    key='adsengine.ads.top',
    label='Top des annonces',
    description=(
        "Quelles sont les 3 meilleures annonces ? Renvoie le classement des "
        "créatifs par performance."),
    endpoint='/api/django/adsengine/reporting/creatifs/classement/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission='adsengine_view',
    risk=RISK_INTERNAL,
)

LISTER_CAMPAGNES = AgentAction(
    key='adsengine.campaigns.list',
    label='Lister les campagnes publicitaires',
    description=(
        "Quelles campagnes publicitaires ai-je ? Renvoie les campagnes miroir "
        "(nom, statut, dépense)."),
    endpoint='/api/django/adsengine/campaigns/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission='adsengine_view',
    risk=RISK_INTERNAL,
)

_ACTIONS = (DEPENSE_SEMAINE, TOP_ADS, LISTER_CAMPAGNES)


def register_actions() -> None:
    """Enregistre les actions LECTURE (idempotent : ignore une clé déjà posée)."""
    for action in _ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
