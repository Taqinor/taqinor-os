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

Permissions (copilote vague 2) : chacune est le code que la ROUTE exige
(``get_permissions`` des viewsets) — ``achats_commander`` pour
``commander-besoin`` (REP3), ``intervention_gerer`` pour la création
d'intervention (REP4). Les deux écrivent sur des données existantes ou dans
la journée de quelqu'un : propositions À CONFIRMER.

Enregistré (idempotent) au démarrage par :func:`register_installation_actions`,
appelée depuis ``InstallationsConfig.ready()``.
"""
from __future__ import annotations

from apps.agent.registry import AgentAction, RISK_OUTWARD, register


# Type d'intervention d'une visite de maintenance : valeur exacte de
# ``Intervention.Type.CONTROLE`` (apps/installations/models_intervention.py).
_VISITE_TYPE = 'controle'


#: REP4 — garde RÉELLE de la création d'intervention : ``IsResponsableOrAdmin``
#: + ``DroitDeLaGrille('intervention_gerer')`` (ASEC72), et
#: ``technicien_assign`` en plus quand le corps porte ``technicien``
#: (``InterventionViewSet.get_permissions``, ASEC50).
_PERM_INTERVENTION = 'intervention_gerer'


# REP4 — une intervention datée entre dans la journée d'un technicien : une
# écriture sur l'agenda de quelqu'un → proposition À CONFIRMER. Le relais
# n'applique pas un ``default`` du schéma alors que ``type_intervention`` est
# obligatoire au modèle : il est REQUIS, à valeur unique (contrôle).
PLANIFIER_VISITE_MAINTENANCE = AgentAction(
    key='installations.intervention.planifier_visite',
    label='Planifier une visite de maintenance',
    description=(
        "Sert à : planifier, après confirmation, une visite de maintenance "
        "(intervention de type contrôle) sur un chantier à une date. Le "
        "technicien désigné est notifié ; sans technicien, la visite n'est "
        "dans la journée de personne (l'installateur du chantier est mis "
        "dans l'équipe). Ne pas utiliser pour : une pose ni la visite "
        "technique d'un lead avant devis (elle se planifie depuis la fiche "
        "du lead). Exemple : « contrôle du "
        "chantier 12 le 2026-12-03 par le technicien 9 » → installation=12, "
        "type_intervention=controle, date_prevue, technicien=9. Résultat : "
        "l'intervention créée ; 409 si le chantier est annulé."
    ),
    endpoint='/api/django/installations/interventions/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'installation': {
                'type': 'integer',
                'title': 'Chantier (id)',
                'description': 'Chantier à visiter.',
            },
            'type_intervention': {
                'type': 'string',
                'title': "Type d'intervention",
                'enum': [_VISITE_TYPE],
                'description': 'Toujours controle.',
            },
            'date_prevue': {
                'type': 'string',
                'format': 'date',
                'title': 'Date prévue',
                'description': 'Date prévue (AAAA-MM-JJ).',
            },
            'technicien': {
                'type': 'integer',
                'title': 'Technicien (id)',
                'description': ('Qui fait la visite (demande-le) ; '
                                "l'affecter exige le droit technicien_assign."),
            },
        },
        'required': ['installation', 'type_intervention', 'date_prevue'],
    },
    required_permission=_PERM_INTERVENTION,
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Planifier une visite de maintenance (contrôle) sur le chantier, à "
        "cette date ; le technicien désigné est notifié."),
    # Vague 2 — l'aperçu NOMME le chantier et le technicien
    # (`selectors_libelles.libelles_installations`, compte résolu par l'agent).
    objets={'installation': 'chantier', 'technicien': 'utilisateur'},
)


#: REP3 — garde RÉELLE de ``commander-besoin`` : ``IsResponsableOrAdmin`` +
#: ``HasPermissionOrLegacy('achats_commander')`` (branche dédiée de
#: ``InstallationViewSet.get_permissions``, ACHT54) — jamais
#: ``installation_gerer`` (le Technicien voyait l'outil et recevait 403).
_PERM_COMMANDER = 'achats_commander'


# REP3 — la route crée des BCF BROUILLONS (un par fournisseur) ET tente de
# faire passer un chantier « Signé » à « Matériel commandé »
# (``_avancer_materiel_commande``, ``exiger_couverture=False``) : deux effets
# sur des données existantes → proposition À CONFIRMER dont l'aperçu dit les
# deux. Corps de la route (``CommanderBesoinRequete``) : ``fournisseur``,
# ``fournisseurs`` {produit_id: fournisseur_id}, ``produits`` [ids].
BROUILLON_COMMANDE_CHANTIER = AgentAction(
    key='installations.chantier.commander_besoin',
    label='Commander les manques du chantier (brouillons)',
    description=(
        "Sert à : créer, après confirmation, les bons de commande "
        "fournisseur BROUILLONS des manques de matériel d'un chantier (un "
        "par fournisseur) ; rien n'est envoyé au fournisseur. Un chantier "
        "« Signé » passe aussi à « Matériel commandé » quand ses étapes le "
        "permettent. Ne pas utiliser pour : envoyer une commande ni une "
        "commande hors chantier. Exemple : « commande ce qui manque pour le "
        "chantier 12 » → id=12. Résultat : les BCF brouillons et le statut du "
        "chantier ; 409 si rien ne manque, si un BCF ouvert couvre déjà ou "
        "sans fournisseur."
    ),
    endpoint='/api/django/installations/chantiers/{id}/commander-besoin/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'title': 'Chantier (id)',
                'description': 'Chantier dont on commande les manques '
                               '(consommé par le gabarit de chemin).',
            },
            'fournisseur': {
                'type': 'integer',
                'title': 'Fournisseur (id)',
                'description': ('Fournisseur imposé aux lignes ; absent : '
                                'celui du produit.'),
            },
            'fournisseurs': {
                'type': 'object',
                'title': 'Fournisseur par produit',
                'additionalProperties': {'type': 'integer'},
                'description': '{"<produit_id>": <fournisseur_id>}.',
            },
            'produits': {
                'type': 'array',
                'title': 'Produits à commander (ids)',
                'items': {'type': 'integer'},
                'description': 'Absent : tous les manques.',
            },
        },
        'required': ['id'],
    },
    required_permission=_PERM_COMMANDER,
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Créer les bons de commande fournisseur BROUILLONS des manques du "
        "chantier (rien n'est envoyé) ; un chantier « Signé » peut passer à "
        "« Matériel commandé »."),
    objets={'id': 'chantier', 'fournisseur': 'fournisseur'},
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
