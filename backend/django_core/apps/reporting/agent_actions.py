"""RPT3 (copilote vague 2) — action du Copilote sur le reporting : les trois « CA ».

Une seule lecture, ``reporting.ca.lire`` : la route
``GET /api/django/reporting/assistant/ca/`` (``views_assistant.py``, contrat
``contract_samples/assistant_ca.json``) rend TOUJOURS le signé HT, le facturé HT
et l'encaissé HT de la période, chacun étiqueté — jamais un « CA » nu, jamais
une marge. Le module est PUREMENT des métadonnées : la route re-vérifie le
droit, la société et la portée du rôle. Découvert par ``apps.agent`` via
``platform.PLATFORM['agent_actions_module']`` (appel de :func:`register_actions`,
idempotent) ; lot ``copilote`` : le modèle ne la voit que copilote allumé.
"""
from __future__ import annotations

from apps.agent.registry import LOT_COPILOTE, RISK_INTERNAL, AgentAction, _REGISTRY, register

_DATE = {'type': 'string', 'format': 'date'}

CA_LIRE = AgentAction(
    key='reporting.ca.lire',
    label="Lire le chiffre d'affaires (signé, facturé, encaissé)",
    description=(
        "Sert à : dire combien l'entreprise a fait entre deux dates, avec "
        "TOUJOURS les trois chiffres HT étiquetés (signé, facturé, encaissé). "
        "Ne pas utiliser pour : une marge, un classement de commerciaux ni un "
        "chiffre par personne. Exemple : « combien on a fait ce mois ? » → du "
        "= 1er du mois, au = aujourd'hui. Résultat : les trois montants HT "
        "avec leur définition ; cite les trois, jamais « le CA » seul."),
    endpoint='/api/django/reporting/assistant/ca/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'du': dict(_DATE, description='Premier jour inclus (AAAA-MM-JJ).'),
            'au': dict(_DATE, description='Dernier jour inclus (AAAA-MM-JJ), '
                                          '366 jours au plus après du.'),
        },
        'required': ['du', 'au'],
    },
    required_permission='reporting_voir',
    risk=RISK_INTERNAL,
    carte='chiffres_ca',
    lot=LOT_COPILOTE,
)

_ACTIONS = (CA_LIRE,)


def register_actions() -> None:
    """Enregistre les actions du reporting (idempotent : ignore une clé déjà posée)."""
    for action in _ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
