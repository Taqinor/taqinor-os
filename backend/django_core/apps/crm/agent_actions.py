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

from datetime import timedelta

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
        "Sert à : créer un lead (opportunité) pour un prospect solaire "
        "(société et responsable posés côté serveur). "
        "Ne pas utiliser pour : un client existant ni modifier un lead. "
        "Exemple : « Ajoute le prospect Karim Alami, Casablanca ». "
        "Résultat : le lead créé ; l'étape initiale vient du modèle."
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
        "Sert à : faire avancer l'étape du pipeline d'un lead et/ou poser sa "
        "date de relance. "
        "Ne pas utiliser pour : ajouter une note (crm.lead.note) ni lister "
        "les relances (crm.leads.a_relancer). "
        "Exemple : « Passe le lead 12 en devis envoyé, relance le 3 »"
        " (étapes = clés de STAGES.py). "
        "Résultat : le lead mis à jour ; la société n'est jamais modifiable."
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
        "Sert à : ajouter une note manuelle (appel, commentaire) au chatter "
        "d'un lead. "
        "Ne pas utiliser pour : changer l'étape (crm.lead.update) ni lire le "
        "lead (crm.lead.resume). "
        "Exemple : « Note sur le lead 12 : client intéressé, rappeler lundi ». "
        "Résultat : la note créée ; auteur et société posés côté serveur."
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
        "Sert à : préparer le texte et le lien `wa.me` d'un ou plusieurs "
        "devis du lead ; n'envoie jamais, le commercial valide lui-même. "
        "Ne pas utiliser pour : une relance sans devis "
        "(crm.lead.brouillon_suivi). "
        "Exemple : « Prépare le WhatsApp du devis 45 pour le lead 12 ». "
        "Résultat : {wa_url, message, links}."
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


# AIC30 — « Mes leads à relancer » : LECTURE de la file du cockpit « contrôle du
# suivi » de l'utilisateur connecté (jamais une copie de la règle de retard).
# Endpoint : GET /api/django/crm/assistant/a-relancer/ (views_assistant).
LEADS_A_RELANCER = AgentAction(
    key='crm.leads.a_relancer',
    label='Mes leads à relancer',
    description=(
        "Sert à : lister les leads que le commercial connecté doit relancer "
        "(nom, étape, touche prévue, retard en jours ouvrés, canal, dernier "
        "contact), 20 lignes max avec le total. "
        "Ne pas utiliser pour : relancer, écrire ou chercher un lead précis. "
        "Exemple : « Qui dois-je relancer aujourd'hui ? » (portee=aujourd_hui). "
        "Résultat : {portee, total, limite, lignes[]}, même file que le cockpit."
    ),
    endpoint='/api/django/crm/assistant/a-relancer/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'portee': {
                'type': 'string',
                'enum': ['aujourd_hui', 'retard', 'semaine'],
                'description': 'Période de la file (défaut aujourd_hui).',
            },
        },
    },
    required_permission='crm_voir',
    risk=RISK_INTERNAL,
)


# AIC31 — « Résume-moi ce lead avant mon appel » : LECTURE assemblée chez chaque
# propriétaire (chatter, devis, visites, cadence). Endpoint :
# GET /api/django/crm/leads/<id>/resume/ (views_assistant.lead_resume).
RESUME_LEAD = AgentAction(
    key='crm.lead.resume',
    label='Résumer un lead',
    description=(
        "Sert à : préparer un appel — identité, étape, contact préféré, "
        "5 dernières entrées du chatter, devis, visites, prochaine touche, "
        "alertes. "
        "Ne pas utiliser pour : écrire une note (crm.lead.note) ni modifier "
        "le lead. "
        "Exemple : « Résume-moi le lead 12 avant mon appel ». "
        "Résultat : {identite, etape, chatter[], devis[], visites[], "
        "prochaine_touche, alertes[]} sans prix d'achat."
    ),
    endpoint='/api/django/crm/leads/{id}/resume/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {'id': {'type': 'integer'}},
        'required': ['id'],
    },
    required_permission='crm_voir',
    risk=RISK_INTERNAL,
)


# AIC32 — brouillon de message de suivi (relance après devis, après visite, réveil
# Froid). Endpoint : POST /api/django/crm/leads/<id>/brouillon-suivi/
# (views_assistant.lead_brouillon_suivi). N'ENVOIE RIEN et n'écrit RIEN : le
# commercial relit le texte puis le copie ou ouvre le lien wa.me lui-même.
BROUILLON_SUIVI = AgentAction(
    key='crm.lead.brouillon_suivi',
    label='Brouillon de message de suivi',
    description=(
        "Sert à : rédiger un TEXTE de suivi (relance devis, après visite, "
        "réveil) à relire puis copier ou ouvrir via wa.me. "
        "Ne pas utiliser pour : envoyer (jamais d'envoi) ni préparer l'envoi "
        "d'un devis (crm.lead.whatsapp_prepare). "
        "Exemple : « Prépare une relance WhatsApp pour le lead 12 ». "
        "Résultat : {texte, lien_wa_me, modele_source, langue_servie}, "
        "500 caractères max sur WhatsApp, expéditeur = responsable du lead."
    ),
    endpoint='/api/django/crm/leads/{id}/brouillon-suivi/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'canal': {'type': 'string',
                      'enum': ['whatsapp', 'sms', 'email']},
            'langue': {'type': 'string', 'enum': ['fr', 'ar'],
                       'description': 'Défaut fr ; ar seulement si un '
                                      'modèle arabe existe.'},
            'objectif': {'type': 'string',
                         'enum': ['relance_devis', 'apres_visite',
                                  'reveil_froid']},
        },
        'required': ['id', 'canal', 'objectif'],
    },
    required_permission='crm_modifier',
    risk=RISK_INTERNAL,
)


# AIC35 — digest du matin (« Mon matin ») : relances du jour (AIC30), visites du
# jour, devis envoyés sans réponse depuis plus de 7 jours, manques signalés hier
# (compte). LECTURE. Permission
# visites_voir : le commercial terrain n'a QUE ses visites (pas de pipeline).
# Endpoint : GET /api/django/crm/assistant/digest-matin/.
DIGEST_MATIN = AgentAction(
    key='crm.digest_matin',
    label='Mon matin',
    description=(
        "Sert à : commencer la journée — relances du jour, visites du jour, "
        "devis envoyés sans réponse depuis plus de 7 jours, manques signalés "
        "hier (10 lignes max par bloc, avec les totaux). "
        "Ne pas utiliser pour : envoyer quoi que ce soit ni détailler un lead "
        "(crm.lead.resume). "
        "Exemple : « Qu'est-ce que j'ai ce matin ? ». "
        "Résultat : {visites, relances, devis_sans_reponse, manques_signales_hier} ; un terrain ne "
        "reçoit que ses visites."
    ),
    endpoint='/api/django/crm/assistant/digest-matin/',
    method='GET',
    inputs={'type': 'object', 'properties': {}},
    required_permission='visites_voir',
    risk=RISK_INTERNAL,
)


_ACTIONS = (
    CREER_LEAD,
    METTRE_A_JOUR_LEAD,
    NOTER_LEAD,
    PREPARER_ENVOI_WHATSAPP,
    LEADS_A_RELANCER,
    RESUME_LEAD,
    BROUILLON_SUIVI,
    DIGEST_MATIN,
)


# AUDV27 (YHARD2) — handler de rollback PILOTE pour ``crm.client.create``
# (l'action est déclarée dans ``apps.agent.registry`` — builtins, RISK_OUTWARD
# — pas dans ce module). Le handler est du code CRM (il connaît ``Client``),
# enregistré dans le registre technique ``apps.agent.services`` — même sens de
# dépendance que l'enregistrement du catalogue ci-dessus (CRM → agent, jamais
# l'inverse : ``apps.agent`` n'importe aucune app métier).
# AANA49 — délai maximal entre la création du client (exécution réelle de
# l'action par le relais) et la confirmation journalisée.
_MARGE_CREATION_AGENT = timedelta(seconds=5)


def _annuler_creation_client(log):
    """Supprime le ``Client`` créé par une action ``crm.client.create``
    confirmée — SAUF si des documents (devis/facture) le référencent déjà
    (``ProtectedError``), auquel cas l'annulation dégrade en NO-OP motivé
    plutôt que de lever une erreur non rattrapée.

    AANA49 (C-AANA-008) — n'annule QUE le client créé PAR CE journal :
    créateur = ``log.user`` et créé au plus tôt
    ``_MARGE_CREATION_AGENT`` avant ``log.confirmed_at``. Un client
    préexistant (journal forgé, client réutilisé) n'est jamais supprimé :
    l'annulation est refusée (409 côté vue), le client reste."""
    from django.db.models import ProtectedError

    from apps.agent.services import ActionNotUndoableError

    from .models import Client

    if not log.object_id:
        return "Aucun client identifié sur ce journal — rien à annuler."
    client = Client.objects.filter(
        pk=log.object_id, company_id=log.company_id).first()
    if client is None:
        return "Client déjà supprimé ou introuvable — rien à annuler."
    cree_par_ce_journal = (
        log.user_id is not None
        and client.created_by_id == log.user_id
        and log.confirmed_at is not None
        and client.date_creation is not None
        and client.date_creation >= log.confirmed_at - _MARGE_CREATION_AGENT
    )
    if not cree_par_ce_journal:
        raise ActionNotUndoableError(
            f"Annulation refusée : ce client n'a pas été créé par l'agent "
            f"(journal #{log.pk}) — il n'est pas supprimé.")
    nom = client.nom
    try:
        client.delete()
    except ProtectedError:
        return (
            f"Client « {nom} » NON supprimé : des documents (devis/facture) "
            "le référencent déjà — annulez-les d'abord.")
    return f"Client « {nom} » supprimé (annulation de sa création)."


def register_crm_actions() -> None:
    """Enregistre les actions CRM dans le registre AG1 (idempotent).

    Sûre si ``CrmConfig.ready()`` est appelée plus d'une fois : on ne
    ré-enregistre pas une clé déjà présente. Enregistre aussi le handler de
    rollback PILOTE de ``crm.client.create`` (AUDV27) — ``register_undo_
    handler`` est lui-même idempotent (dernier appel gagne).
    """
    for action in _ACTIONS:
        if action.key not in _REGISTRY:
            register(action)

    from apps.agent.services import register_undo_handler
    register_undo_handler('crm.client.create', _annuler_creation_client)
