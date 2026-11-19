"""AG8 — Actions agentiques SAV (catalogue déclaré en code).

Déclare les actions SAV que l'agent (relais FastAPI + JWT utilisateur) peut
proposer, et les enregistre dans le registre AG1 (`apps.agent.registry`). Ce
module est PUREMENT des métadonnées : aucune exécution ici. À l'exécution,
FastAPI relaie le JWT vers l'``endpoint`` nommé et Django re-vérifie permission
+ société.

`ouvrir_ticket_sav` est la version « registre » de l'outil FastAPI hard-codé du
même nom : même endpoint (`POST /api/django/sav/tickets/`), même permission
(`sav_gerer`) ; la société est posée côté serveur (jamais dans le corps).
`mettre_a_jour_ticket` met à jour un ticket existant
(`PATCH …/tickets/<id>/`).

REP5 (copilote vague 2) — les deux écrivent (un ticket neuf, un ticket
existant) : propositions À CONFIRMER, plus jamais exécutées au vol ; les
valeurs des indices sont les valeurs EXACTES du modèle (sans accent).
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_OUTWARD, register


# Permission ERP requise pour ouvrir/mettre à jour un ticket SAV
# (identique au TicketViewSet : write actions → 'sav_gerer').
_SAV_PERMISSION = 'sav_gerer'

#: Valeurs EXACTES de ``Ticket.Priorite`` / ``Ticket.Type``
#: (apps/sav/models.py) — « préventif » accentué était refusé (400).
PRIORITES_TICKET = ('basse', 'normale', 'haute', 'urgente')
TYPES_TICKET = ('correctif', 'preventif')

_PRIORITE = {'type': 'string', 'title': 'Priorité',
             'enum': list(PRIORITES_TICKET)}


OUVRIR_TICKET_SAV = AgentAction(
    key='sav.ticket.create',
    label='Ouvrir un ticket SAV',
    description=(
        "Sert à : ouvrir, après confirmation, un ticket SAV (panne, "
        "réclamation) pour un client OU pour un équipement du parc (client "
        "et chantier sont alors déduits de l'équipement). Ne pas utiliser "
        "pour : changer le statut d'un ticket ni noter un ticket existant. "
        "Exemple : « l'onduleur de M. Benali est en panne » → equipement (ou "
        "client), description avec ses mots, type=correctif. Résultat : le "
        "ticket créé ; 409 si un ticket identique vient d'être ouvert ou si "
        "le client ne peut pas être déduit."
    ),
    endpoint='/api/django/sav/tickets/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'client': {
                'type': 'integer', 'title': 'Client',
                'description': 'Client concerné (ou equipement).',
            },
            'equipement': {
                'type': 'integer', 'title': 'Équipement (id)',
                'description': 'Équipement du parc concerné (ou client).',
            },
            'description': {
                'type': 'string', 'title': 'Description',
                'description': 'Le problème, avec les mots du client.',
            },
            'installation': {
                'type': 'integer', 'title': 'Chantier (id)',
                'description': 'Chantier concerné (optionnel).',
            },
            'priorite': _PRIORITE,
            'type': {'type': 'string', 'title': 'Type',
                     'enum': list(TYPES_TICKET)},
        },
        'required': ['description'],
    },
    required_permission=_SAV_PERMISSION,
    risk=RISK_OUTWARD,
    confirm_summary='Ouvrir un ticket SAV.',
    # Vague 2 — l'aperçu NOMME l'équipement et le chantier
    # (`selectors_libelles.libelles_sav`, `libelles_installations`).
    objets={'client': 'client', 'equipement': 'equipement',
            'installation': 'chantier'},
)


METTRE_A_JOUR_TICKET = AgentAction(
    key='sav.ticket.update',
    label='Mettre à jour un ticket SAV',
    description=(
        "Sert à : changer, après confirmation, la priorité ou la description "
        "d'un ticket SAV existant. Ne pas utiliser pour : changer le statut "
        "(planifier, démarrer, résoudre, clôturer : gestes de l'écran SAV) "
        "ni réaffecter le ticket. Exemple : « passe le ticket 88 en urgent » "
        "→ id=88, priorite=urgente. Résultat : le ticket mis à jour ; la "
        "société reste celle du ticket."
    ),
    endpoint='/api/django/sav/tickets/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer', 'title': 'Ticket (id)',
                'description': 'Identifiant du ticket à mettre à jour.',
            },
            'priorite': _PRIORITE,
            'description': {'type': 'string', 'title': 'Description'},
        },
        'required': ['id'],
    },
    required_permission=_SAV_PERMISSION,
    risk=RISK_OUTWARD,
    confirm_summary='Modifier ce ticket SAV.',
    objets={'id': 'ticket'},
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
