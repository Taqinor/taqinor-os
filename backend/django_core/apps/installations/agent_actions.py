"""AG9 — Actions agentiques de l'app installations (chantiers / interventions).

Déclare en code, via le registre AG1 (:mod:`apps.agent.registry`), les deux
actions que l'agent (relais FastAPI + JWT utilisateur) peut proposer sur le
module chantiers/installations. Ce sont les remplaçantes-catalogue des deux
outils LangChain aujourd'hui codés en dur dans
``backend/fastapi_ia/app/services/action_tools.py`` :

* ``planifier_visite_maintenance`` → ``POST /api/django/installations/interventions/``
  (intervention de type ``controle`` planifiée sur un chantier à une date) ;
* ``brouillon_commande_chantier`` → ``POST
  /api/django/installations/chantiers/{id}/commander-besoin/`` (bon de commande
  fournisseur BROUILLON pour les manques d'un chantier).

Le module est PUREMENT des métadonnées : aucune exécution ici. L'exécution
garde le motif existant — FastAPI relaie le JWT de l'utilisateur vers
l'``endpoint`` nommé, et Django re-vérifie la permission + la société à ce
moment-là. Le ``company`` n'apparaît JAMAIS dans les ``inputs`` (forcé côté
serveur). Pour ``commander-besoin``, le ``<id>`` du chantier est modélisé comme
un input requis que le gabarit de chemin consomme.

Permission requise : ``installation_gerer`` (la permission ERP que les deux
outils FastAPI exigent — ``_BC_PERMS`` / ``_VISITE_PERMS``).

Enregistré (idempotent) au démarrage par :func:`register_installation_actions`,
appelée depuis ``InstallationsConfig.ready()``.
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_INTERNAL, register


# Permission ERP exigée par les deux outils FastAPI d'origine
# (_BC_PERMS / _VISITE_PERMS = installation_gerer/chantier_gerer ; on retient la
# permission canonique installation_gerer).
_PERM_GERER = 'installation_gerer'

# Type d'intervention d'une visite de maintenance (miroir de _VISITE_TYPE).
_VISITE_TYPE = 'controle'


PLANIFIER_VISITE_MAINTENANCE = AgentAction(
    key='installations.intervention.planifier_visite',
    label='Planifier une visite de maintenance',
    description=(
        "Planifie une visite de maintenance (intervention de type contrôle) "
        "sur un chantier à une date donnée (AAAA-MM-JJ). Remplaçante-catalogue "
        "de l'outil FastAPI planifier_visite_maintenance : crée l'intervention "
        "via l'endpoint interventions ; la société est forcée côté serveur."
    ),
    endpoint='/api/django/installations/interventions/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'installation': {
                'type': 'integer',
                'description': 'Chantier à visiter.',
            },
            'type_intervention': {
                'type': 'string',
                'description': "Type d'intervention.",
                'default': _VISITE_TYPE,
            },
            'date_prevue': {
                'type': 'string',
                'description': 'Date prévue (AAAA-MM-JJ).',
            },
            'technicien': {
                'type': 'integer',
                'description': 'Technicien assigné (optionnel).',
            },
        },
        'required': ['installation', 'date_prevue'],
    },
    required_permission=_PERM_GERER,
    risk=RISK_INTERNAL,
    confirm_summary='Planifier une visite de maintenance sur le chantier.',
)


BROUILLON_COMMANDE_CHANTIER = AgentAction(
    key='installations.chantier.commander_besoin',
    label='Brouillonner un bon de commande chantier',
    description=(
        "Crée un bon de commande fournisseur BROUILLON pour les manques de "
        "matériel d'un chantier. Remplaçante-catalogue de l'outil FastAPI "
        "brouillon_bon_commande_chantier : appelle l'endpoint commander-besoin "
        "du chantier ; la société est forcée côté serveur, le brouillon reste à "
        "confirmer manuellement."
    ),
    endpoint='/api/django/installations/chantiers/{id}/commander-besoin/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'Chantier dont on commande les manques '
                               '(consommé par le gabarit de chemin).',
            },
            'fournisseur': {
                'type': 'integer',
                'description': 'Fournisseur (optionnel).',
            },
        },
        'required': ['id'],
    },
    required_permission=_PERM_GERER,
    risk=RISK_INTERNAL,
    confirm_summary='Créer un bon de commande fournisseur brouillon pour les '
                    'manques du chantier.',
)


# Catalogue déclaré par cette app (ordre stable).
INSTALLATIONS_ACTIONS = (
    PLANIFIER_VISITE_MAINTENANCE,
    BROUILLON_COMMANDE_CHANTIER,
)


def register_installation_actions() -> None:
    """Enregistre les actions de l'app installations dans le registre AG1.

    Idempotent : une action déjà présente (même ``key``) n'est pas
    ré-enregistrée — sûr si le module est importé plusieurs fois (tests,
    rechargement du serveur de dev).
    """
    from apps.agent import registry as _registry

    for action in INSTALLATIONS_ACTIONS:
        if action.key not in _registry._REGISTRY:
            register(action)
