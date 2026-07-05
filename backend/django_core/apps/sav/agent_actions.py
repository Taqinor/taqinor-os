"""AG8 — Actions agentiques SAV (catalogue déclaré en code).

Déclare les actions SAV que l'agent (relais FastAPI + JWT utilisateur) peut
proposer, et les enregistre dans le registre AG1 (`apps.agent.registry`). Ce
module est PUREMENT des métadonnées : aucune exécution ici. À l'exécution,
FastAPI relaie le JWT vers l'``endpoint`` nommé et Django re-vérifie permission
+ société.

`ouvrir_ticket_sav` est la version « registre » de l'outil FastAPI hard-codé du
même nom : même endpoint (`POST /api/django/sav/tickets/`), même permission
(`sav_gerer`), `client` requis, et la société est posée côté serveur (jamais
dans le corps). `mettre_a_jour_ticket` met à jour un ticket existant
(`PATCH …/tickets/<id>/`).
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_INTERNAL, register


# Permission ERP requise pour ouvrir/mettre à jour un ticket SAV
# (identique au TicketViewSet : write actions → 'sav_gerer').
_SAV_PERMISSION = 'sav_gerer'


OUVRIR_TICKET_SAV = AgentAction(
    key='sav.ticket.create',
    label='Ouvrir un ticket SAV',
    description=(
        "Ouvre un nouveau ticket SAV (service après-vente) pour un client. À "
        "utiliser quand l'utilisateur demande de créer/ouvrir un ticket ou de "
        "signaler une panne. La société est posée côté serveur."
    ),
    endpoint='/api/django/sav/tickets/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'client': {
                'type': 'integer',
                'description': 'Identifiant du client concerné.',
            },
            'description': {
                'type': 'string',
                'description': 'Description du problème SAV.',
            },
            'installation': {
                'type': 'integer',
                'description': 'Chantier concerné (optionnel).',
            },
            'priorite': {
                'type': 'string',
                'description': 'basse, normale, haute ou urgente.',
            },
            'type': {
                'type': 'string',
                'description': 'correctif ou préventif.',
            },
        },
        'required': ['client'],
    },
    required_permission=_SAV_PERMISSION,
    risk=RISK_INTERNAL,
)


METTRE_A_JOUR_TICKET = AgentAction(
    key='sav.ticket.update',
    label='Mettre à jour un ticket SAV',
    description=(
        "Met à jour un ticket SAV existant (priorité, description, "
        "technicien responsable…). La société reste celle du ticket. "
        "YDOCF1 — le statut ne se change plus par ce PATCH (machine d'états "
        "gardée) : utiliser les actions dédiées "
        "planifier/demarrer/resoudre/cloturer sur "
        "/api/django/sav/tickets/{id}/<action>/."
    ),
    endpoint='/api/django/sav/tickets/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'Identifiant du ticket à mettre à jour.',
            },
            'priorite': {'type': 'string'},
            'description': {'type': 'string'},
            'technicien_responsable': {'type': 'integer'},
        },
        'required': ['id'],
    },
    required_permission=_SAV_PERMISSION,
    risk=RISK_INTERNAL,
)


def register_actions() -> None:
    """Enregistre les actions SAV dans le registre AG1 (idempotent).

    Appelée depuis ``SavConfig.ready()`` via un import fonction-local. Ignore
    silencieusement les ré-enregistrements pour rester sûr si ``ready()`` est
    appelé plusieurs fois (tests, autoreload).
    """
    for action in (OUVRIR_TICKET_SAV, METTRE_A_JOUR_TICKET):
        try:
            register(action)
        except ValueError:
            # Déjà enregistrée — registre déterministe, rien à faire.
            pass
