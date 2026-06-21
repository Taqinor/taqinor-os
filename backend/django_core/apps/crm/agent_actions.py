"""AG6 — Actions agentiques de l'app CRM (catalogue déclaré en code).

Déclare, via le registre AG1 (:mod:`apps.agent.registry`), les actions CRM
« lead » que l'agent (relais FastAPI + JWT utilisateur) peut PROPOSER. Ce module
ne contient AUCUNE logique d'exécution et AUCUN nouvel endpoint : il décrit — en
métadonnées — des écritures qui passent par le ``LeadViewSet`` existant, lequel
re-vérifie permission (rôle) ET société à l'exécution.

Multi-tenant : ``company`` n'apparaît JAMAIS dans le schéma ``inputs`` — la
société est forcée côté serveur (``TenantMixin`` / ``perform_create`` à partir de
``request.user.company``) ; elle ne doit jamais provenir du corps de la requête.

Étapes du pipeline : les valeurs autorisées de ``stage`` viennent de ``STAGES.py``
(racine du dépôt) — JAMAIS codées en dur ici (règle non-négociable #2).

Permissions : le ``LeadViewSet`` garde ses écritures derrière
``IsResponsableOrAdmin`` (un gardien basé sur le RÔLE, pas un code ERP). Comme le
filtre catalogue AG1 (``for_user``) ne sait raisonner que sur des codes ERP, on
adosse ces actions au code ERP le plus proche (``crm_creer`` pour la création,
``crm_modifier`` pour les mises à jour / notes / préparation WhatsApp), portés par
Responsable/Admin/Directeur. Le viewset reste l'autorité finale (il re-vérifie le
rôle + la société).

Enregistrement : :func:`register_crm_actions` est appelée depuis
``CrmConfig.ready()`` (import différé pour éviter les effets de bord à l'import).
Idempotente : sans danger si ``ready()`` est invoquée plusieurs fois.
"""
from __future__ import annotations

from apps.crm.stages import STAGES

from apps.agent.registry import AgentAction, RISK_INTERNAL, register, _REGISTRY


# Action 1 — Créer un lead (opportunité solaire).
# Endpoint réel : POST /api/django/crm/leads/ (LeadViewSet). La société est
# forcée côté serveur (perform_create) ; le responsable par défaut est appliqué
# si aucun owner n'est fourni.
CREER_LEAD = AgentAction(
    key='crm.lead.create',
    label='Créer un lead',
    description=(
        "Crée un nouveau lead (opportunité) pour un prospect solaire. La "
        "société et le responsable par défaut sont attribués côté serveur ; "
        "l'étape initiale est gérée par le modèle."
    ),
    endpoint='/api/django/crm/leads/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'nom': {'type': 'string'},
            'prenom': {'type': 'string'},
            'societe': {'type': 'string'},
            'email': {'type': 'string'},
            'telephone': {'type': 'string'},
            'whatsapp': {'type': 'string'},
            'ville': {'type': 'string'},
            'source': {'type': 'string'},
        },
        'required': ['nom'],
    },
    required_permission='crm_creer',
    risk=RISK_INTERNAL,
)


# Action 2 — Mettre à jour un lead : avancer l'étape du pipeline et/ou poser une
# date de relance. Endpoint réel : PATCH /api/django/crm/leads/<id>/ (LeadViewSet
# .partial_update). Les valeurs de `stage` proviennent de STAGES.py (jamais codées
# en dur). La société reste celle du caller (jamais modifiable depuis le corps).
METTRE_A_JOUR_LEAD = AgentAction(
    key='crm.lead.update',
    label='Mettre à jour un lead',
    description=(
        "Met à jour un lead : fait avancer l'étape du pipeline et/ou pose une "
        "date de relance. Les étapes valides sont les clés canoniques de "
        "STAGES.py. La société du lead n'est jamais modifiable depuis le corps."
    ),
    endpoint='/api/django/crm/leads/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'stage': {
                'type': 'string',
                # Source de vérité unique des étapes : STAGES.py (règle #2).
                'enum': list(STAGES),
                'description': "Étape du pipeline (clé canonique STAGES.py).",
            },
            'relance_date': {
                'type': 'string',
                'format': 'date',
                'description': 'Date de relance (YYYY-MM-DD).',
            },
        },
        'required': ['id'],
    },
    required_permission='crm_modifier',
    risk=RISK_INTERNAL,
)


# Action 3 — Noter un lead (note manuelle / journal d'appel dans le chatter).
# Endpoint réel : POST /api/django/crm/leads/<id>/noter/ (LeadViewSet.noter).
# L'auteur et la société sont pris de la requête côté serveur, jamais du corps.
NOTER_LEAD = AgentAction(
    key='crm.lead.note',
    label='Noter un lead',
    description=(
        "Ajoute une note manuelle (appel, commentaire…) au chatter du lead. "
        "L'auteur et la société sont posés côté serveur ; jamais lus du corps."
    ),
    endpoint='/api/django/crm/leads/{id}/noter/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'body': {'type': 'string'},
        },
        'required': ['id', 'body'],
    },
    required_permission='crm_modifier',
    risk=RISK_INTERNAL,
)


# Action 4 — Préparer l'envoi WhatsApp d'un/de devis du lead. Endpoint réel :
# POST /api/django/crm/leads/<id>/whatsapp-devis/ (LeadViewSet.whatsapp_devis).
# N'ENVOIE RIEN : renvoie {wa_url, message, links} pour la carte de résultat ;
# le commercial appuie lui-même sur Envoyer. Effet interne (préparation), donc
# RISK_INTERNAL.
PREPARER_ENVOI_WHATSAPP = AgentAction(
    key='crm.lead.whatsapp_prepare',
    label='Préparer un envoi WhatsApp de devis',
    description=(
        "Prépare un lien wa.me pré-rempli pour un ou plusieurs devis du lead "
        "et renvoie {wa_url, message, links} pour la carte de résultat. "
        "N'envoie rien : le commercial valide l'envoi manuellement."
    ),
    endpoint='/api/django/crm/leads/{id}/whatsapp-devis/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'devis_ids': {
                'type': 'array',
                'items': {'type': 'integer'},
                'description': 'Identifiants des devis du lead à inclure.',
            },
            'langue': {
                'type': 'string',
                'description': "Langue du message ('fr' | 'ar'…) ; défaut = lead.",
            },
        },
        'required': ['id', 'devis_ids'],
    },
    required_permission='crm_modifier',
    risk=RISK_INTERNAL,
)


_ACTIONS = (
    CREER_LEAD,
    METTRE_A_JOUR_LEAD,
    NOTER_LEAD,
    PREPARER_ENVOI_WHATSAPP,
)


def register_crm_actions() -> None:
    """Enregistre les actions CRM dans le registre AG1 (idempotent).

    Sûre si ``CrmConfig.ready()`` est appelée plus d'une fois : on ne
    ré-enregistre pas une clé déjà présente.
    """
    for action in _ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
