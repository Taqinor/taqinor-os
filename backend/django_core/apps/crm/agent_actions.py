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

from apps.crm.stages import COLD, SIGNED, STAGES

from apps.agent.registry import (
    AgentAction, LOT_COPILOTE, LOT_HERITE, RISK_INTERNAL, RISK_OUTWARD,
    register, _REGISTRY)


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
    # COP-C5 — UNE seule définition effective de ``crm.lead.create`` : la
    # création reste CONFIRMÉE (la lane REGISTRE retire le doublon du registre).
    risk=RISK_OUTWARD,
)


# Action 2 — Poser la date de relance d'un lead. Endpoint réel : PATCH
# /api/django/crm/leads/<id>/ (LeadViewSet.partial_update). COP-C5 : ``stage``
# n'est PLUS porté ici (un saut d'étape sans confirmation, jusqu'à SIGNED sans
# devis accepté) — il vit dans ``crm.lead.changer_etape``, confirmé. La société
# reste celle du caller (jamais modifiable depuis le corps). Une date de
# relance déplace la prochaine touche (MRY10) : écriture CONFIRMÉE.
METTRE_A_JOUR_LEAD = AgentAction(
    key='crm.lead.update',
    label='Mettre à jour un lead',
    description=(
        "Sert à : poser la date de relance d'un lead (la prochaine touche "
        "du suivi est déplacée à cette date). "
        "Ne pas utiliser pour : changer l'étape (crm.lead.changer_etape), "
        "noter (crm.lead.note), qualifier le lead ni enregistrer la réponse "
        "d'une touche. "
        "Exemple : « Relance le lead 12 le 3 ». "
        "Résultat : le lead mis à jour ; la société n'est jamais modifiable."
    ),
    endpoint='/api/django/crm/leads/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'relance_date': {
                'type': 'string',
                'format': 'date',
                'description': 'Date de relance (YYYY-MM-DD).',
            },
        },
        'required': ['id'],
    },
    required_permission='crm_modifier',
    risk=RISK_OUTWARD,
    objets={'id': 'lead'},
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
        "Ne pas utiliser pour : changer l'étape (crm.lead.changer_etape) ni "
        "lire le lead (crm.lead.resume). "
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


# Action 4 — Préparer l'envoi WhatsApp d'un/de devis du lead. AMSG6 — endpoint :
# l'APERÇU sans effet (QJR538 : ni « envoyé », ni funnel, ni AuditLog), jamais
# le commit `whatsapp-devis` ; COP-C7 : la vue mince de l'assistant
# (``views_assistant.lead_whatsapp_devis_apercu``) rend en plus ``lead_id`` et
# ``devis_ids`` — la carte « wa_devis » s'en sert pour appeler le commit au
# moment où elle ouvre WhatsApp. Le commercial appuie lui-même sur Envoyer.
PREPARER_ENVOI_WHATSAPP = AgentAction(
    key='crm.lead.whatsapp_prepare',
    label='Préparer un envoi WhatsApp de devis',
    description=(
        "Sert à : préparer le texte et le lien `wa.me` d'un ou plusieurs "
        "devis du lead ; n'envoie jamais, le commercial valide lui-même. "
        "Ne pas utiliser pour : une relance sans devis (le texte d'une "
        "touche du suivi). "
        "Exemple : « Prépare le WhatsApp du devis 45 pour le lead 12 ». "
        "Résultat : {wa_url, message, links, lead_id, devis_ids}."
    ),
    endpoint='/api/django/crm/assistant/leads/{id}/whatsapp-devis-apercu/',
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
    carte='wa_devis',
)


# AIC30 — « Mes leads à relancer » : LECTURE de la file du cockpit « contrôle du
# suivi » de l'utilisateur connecté (jamais une copie de la règle de retard).
# Endpoint : GET /api/django/crm/assistant/a-relancer/ (views_assistant).
LEADS_A_RELANCER = AgentAction(
    key='crm.leads.a_relancer',
    label='Mes leads à relancer',
    description=(
        "Sert à : lister les leads que le commercial connecté doit relancer "
        "(nom, étape, touche prévue, retard, canal, dernier contact), 20 "
        "lignes max avec le total ; chaque ligne porte le touche_id de sa "
        "touche. "
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
    carte='file_touches',
)


# AIC31 — « Résume-moi ce lead avant mon appel » : LECTURE assemblée chez chaque
# propriétaire (chatter, devis, visites, cadence). Endpoint :
# GET /api/django/crm/leads/<id>/resume/ (views_assistant.lead_resume).
RESUME_LEAD = AgentAction(
    key='crm.lead.resume',
    label='Résumer un lead',
    description=(
        "Sert à : préparer un appel — identité, étape, contact préféré, "
        "5 dernières entrées du chatter, devis (avec leur id), visites, "
        "prochaine touche (avec son touche_id), alertes. "
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
    carte='fiche_lead',
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
        "Résultat : {texte, wa_url, modele_source, langue_servie}, 500 "
        "caractères max sur WhatsApp ; sans modèle société le texte est vide "
        "(aucune phrase de repli)."
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
    # COP-C7 — le copilote lui préfère ``crm.suivi.preparer_touche`` (les
    # textes VALIDÉS du suivi) : il ne reste servi que copilote éteint.
    carte='wa_message',
    lot=LOT_HERITE,
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
    carte='matin',
)


# ── COP — copilote commercial : les actions NEUVES ────────────────────────────
# Toute action neuve naît dans le lot ``copilote`` (invisible des commerciaux
# tant que l'interrupteur ASSISTANT_COPILOTE ne les allume pas). Les
# vocabulaires (issues, réponses, langues, clés de message…) sont LUS là où le
# serveur les valide — jamais retapés : un test de parité les compare.

#: Champs de la fiche qu'une QUALIFICATION à l'appel a le droit d'écrire
#: (les questions du Guide : factures, toit, foyer, équipements, projet).
#: Jamais ``stage``, jamais un champ de propriété (owner), de parcage ni de
#: contact (téléphone, e-mail : un faux numéro enverrait le prochain WhatsApp
#: à une autre personne).
CHAMPS_QUALIFICATION = (
    'facture_hiver', 'facture_ete', 'ete_differente', 'conso_mensuelle_kwh',
    'distributeur', 'raccordement', 'regularisation_8221', 'objectif_projet',
    'type_toiture', 'surface_toiture_m2', 'orientation', 'ombrage',
    'batterie_souhaitee', 'type_bien', 'ville',
    'occupation_jour', 'nb_personnes_foyer', 'chauffage_electrique_hiver',
    'ownership', 'equip_piscine', 'equip_voiture_electrique', 'equip_clim',
    'equip_chauffe_eau_electrique', 'equip_ve_statut',
    'project_timeline', 'financing_intent', 'decideur', 'devis_concurrents',
    'frein_principal', 'declencheur', 'type_installation',
    'taille_souhaitee_kwc', 'langue_preferee', 'civilite', 'priorite',
)


def _propriete_du_champ(champ):
    """Le schéma JSON d'un champ du lead, LU sur le modèle : choix fermés en
    ``enum`` (les valeurs du serveur), booléen, entier, nombre ou texte."""
    from django.db import models

    from apps.crm.models import Lead

    f = Lead._meta.get_field(champ)
    propriete = {'description': str(f.verbose_name)}
    if f.choices:
        propriete.update(
            type='string', enum=[v for v, _libelle in f.flatchoices if v != ''])
    elif isinstance(f, models.BooleanField):
        propriete['type'] = 'boolean'
    elif isinstance(f, models.IntegerField):
        propriete['type'] = 'integer'
    elif isinstance(f, (models.DecimalField, models.FloatField)):
        propriete['type'] = 'number'
    else:
        propriete['type'] = 'string'
    return propriete


def _vocabulaire_touche():
    """Les vocabulaires de ``fait`` / ``reporter`` / ``sauter``, lus chez le
    serveur : issues du chatter, réponses du client, raisons d'attente,
    langues de relance, gestes."""
    from apps.crm.assistant_touches import GESTES
    from apps.crm.cadence_reponses import (
        RAISONS_ATTENTE_VALEURS, REPONSES_TOUCHE)
    from apps.crm.models import LeadActivity
    from apps.crm.schema_docs import LANGUES_RELANCE

    return {
        'gestes': list(GESTES),
        'issues': [k for k, _libelle in LeadActivity.OUTCOMES if k],
        'reponses': list(REPONSES_TOUCHE),
        'raisons': list(RAISONS_ATTENTE_VALEURS),
        'langues': list(LANGUES_RELANCE),
    }


def _entrees_proposer_reponse():
    voc = _vocabulaire_touche()
    return {
        'type': 'object',
        'properties': {
            'touche_id': {'type': 'integer',
                          'description': 'touche_id de la file ou de la fiche.'},
            'geste': {'type': 'string', 'enum': voc['gestes'],
                      'description': 'fait = répondre ; reporter ; sauter.'},
            'outcome': {'type': 'string', 'enum': voc['issues'],
                        'description': 'Issue (geste fait).'},
            'reponse': {'type': 'string', 'enum': voc['reponses'],
                        'description': 'Réponse du client (geste fait) : '
                                       'prime sur outcome.'},
            'motif_refus': {'type': 'string',
                            'description': 'Motif (avec outcome=refuse).'},
            'perdu_junk': {'type': 'string',
                           'description': 'Motif junk (outcome=non_joint).'},
            'motif_perte': {'type': 'string',
                            'description': 'Motif (reponse=perdu).'},
            'raison_attente': {'type': 'string', 'enum': voc['raisons'],
                               'description': 'reponse=attente_accord.'},
            'rappel_le': {'type': 'string', 'format': 'date',
                          'description': 'AAAA-MM-JJ ; pas dans le passé.'},
            'rappel_heure': {'type': 'string', 'description': 'HH:MM.'},
            'note': {'type': 'string'},
            'langue': {'type': 'string', 'enum': voc['langues']},
            'mode': {'type': 'string', 'enum': ['decaler', 'veille'],
                     'description': 'geste reporter (date : rappel_le).'},
        },
        'required': ['touche_id', 'geste'],
    }


def _entrees_qualifier():
    proprietes = {'id': {'type': 'integer'}}
    proprietes.update(
        {champ: _propriete_du_champ(champ) for champ in CHAMPS_QUALIFICATION})
    return {'type': 'object', 'properties': proprietes, 'required': ['id']}


def _entrees_journaliser():
    from apps.crm.models import LeadActivity

    return {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'kind': {'type': 'string', 'enum': [
                LeadActivity.Kind.APPEL, LeadActivity.Kind.EMAIL,
                LeadActivity.Kind.WHATSAPP]},
            'body': {'type': 'string', 'description': "Résumé de l'échange."},
            'outcome': {'type': 'string', 'enum': [
                k for k, _libelle in LeadActivity.OUTCOMES if k]},
            'rappel_le': {'type': 'string', 'format': 'date'},
            'rappel_heure': {'type': 'string', 'description': 'HH:MM.'},
        },
        'required': ['id', 'kind'],
    }


def _entrees_message_visite():
    from apps.crm.cadence_messages import CLES_MESSAGE_VISITE
    from apps.crm.schema_docs import LANGUES_RELANCE

    return {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'cle': {'type': 'string', 'enum': list(CLES_MESSAGE_VISITE)},
            'langue': {'type': 'string', 'enum': list(LANGUES_RELANCE),
                       'description': 'Défaut : la langue du lead.'},
        },
        'required': ['id', 'cle'],
    }


CHERCHER_LEAD = AgentAction(
    key='crm.lead.chercher',
    label='Retrouver un lead',
    description=(
        "Sert à : retrouver un lead par nom, prénom, société, téléphone, "
        "ville ou référence (et/ou étape), 10 lignes par défaut. "
        "Ne pas utiliser pour : lister toute la file (crm.leads.a_relancer) "
        "ni lire une fiche (crm.lead.resume). "
        "Exemple : « Le lead de Bouskoura », « retrouve Alami ». "
        "Résultat : {q, etape, total, limite, lignes[]} ; chaque ligne porte "
        "lead_id et, si ouverte, prochaine_touche.touche_id."
    ),
    endpoint='/api/django/crm/assistant/leads/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'q': {'type': 'string'},
            'etape': {'type': 'string', 'enum': list(STAGES),
                      'description': 'Étape du pipeline (clé STAGES.py).'},
            'limite': {'type': 'integer', 'minimum': 1, 'maximum': 25},
        },
    },
    required_permission='crm_voir',
    risk=RISK_INTERNAL,
    carte='liste_leads',
    lot=LOT_COPILOTE,
)

PREPARER_TOUCHE = AgentAction(
    key='crm.suivi.preparer_touche',
    label='Préparer une touche du suivi',
    description=(
        "Sert à : préparer UNE touche de la file — le message VALIDÉ du "
        "suivi (texte rendu par le serveur, jamais écrit par toi) ou le "
        "script d'appel et ses questions. Rien n'est envoyé. "
        "Ne pas utiliser pour : enregistrer la réponse du client "
        "(crm.suivi.proposer_reponse). "
        "Exemple : « Prépare ma prochaine relance » (touche_id de la file). "
        "Résultat : {touche, lead, message | appel | refus}."
    ),
    endpoint='/api/django/crm/assistant/touches/{touche_id}/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {'touche_id': {'type': 'integer'}},
        'required': ['touche_id'],
    },
    required_permission='crm_voir',
    risk=RISK_INTERNAL,
    carte='touche',
    lot=LOT_COPILOTE,
)

PROPOSER_REPONSE = AgentAction(
    key='crm.suivi.proposer_reponse',
    label="Proposer la réponse d'une touche",
    description=(
        "Sert à : afficher la carte de la réponse que la commerciale vient "
        "de dicter (pas de réponse, rappel jeudi 11 h, refus…) ; le serveur "
        "la valide. Cet outil n'enregistre RIEN : c'est son doigt sur la "
        "carte qui confirme. Une seule touche à la fois. "
        "Ne pas utiliser pour : écrire au client ni noter (crm.lead.note). "
        "Exemple : « Il n'a pas répondu » (geste=fait, outcome=non_joint). "
        "Résultat : {proposition {libelle, effet}} ou proposition_refus."
    ),
    endpoint='/api/django/crm/assistant/touches/{touche_id}/',
    method='GET',
    inputs=_entrees_proposer_reponse(),
    required_permission='crm_voir',
    risk=RISK_INTERNAL,
    carte='touche',
    lot=LOT_COPILOTE,
)

QUALIFIER_LEAD = AgentAction(
    key='crm.lead.qualifier',
    label='Qualifier un lead',
    description=(
        "Sert à : écrire sur la fiche ce que le client a dit à l'appel "
        "(factures, toit, foyer, équipements, délai, financement, décideur, "
        "frein). "
        "Ne pas utiliser pour : l'étape (crm.lead.changer_etape), le "
        "responsable, le parcage, le téléphone ni l'e-mail. "
        "Exemple : « Facture 2 300 en été, 1 400 en hiver, il décide avec "
        "son frère ». "
        "Résultat : le lead mis à jour, après confirmation."
    ),
    endpoint='/api/django/crm/leads/{id}/',
    method='PATCH',
    inputs=_entrees_qualifier(),
    required_permission='crm_modifier',
    risk=RISK_OUTWARD,
    lot=LOT_COPILOTE,
    objets={'id': 'lead'},
)

CHANGER_ETAPE_LEAD = AgentAction(
    key='crm.lead.changer_etape',
    label="Changer l'étape d'un lead",
    description=(
        "Sert à : faire AVANCER un lead dans le pipeline (étapes = clés de "
        "STAGES.py), après confirmation. "
        "Ne pas utiliser pour : signer (l'acceptation d'un devis le fait), "
        "parquer au Froid (geste de l'écran avec sa raison) ni reculer. "
        "Exemple : « Passe le lead 12 en devis envoyé ». "
        "Résultat : le lead mis à jour."
    ),
    endpoint='/api/django/crm/leads/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'stage': {
                'type': 'string',
                # Source unique : STAGES.py (règle #2), SIGNED et COLD exclus.
                'enum': [s for s in STAGES if s not in (SIGNED, COLD)],
                'description': "Étape du pipeline (clé canonique STAGES.py).",
            },
        },
        'required': ['id', 'stage'],
    },
    required_permission='crm_modifier',
    risk=RISK_OUTWARD,
    objets={'id': 'lead'},
)

JOURNALISER_LEAD = AgentAction(
    key='crm.lead.journaliser',
    label='Journaliser un échange',
    description=(
        "Sert à : consigner au fil du lead un appel, un e-mail ou un "
        "WhatsApp déjà passé (premier contact horodaté ; outcome=rappel "
        "déplace la prochaine touche), après confirmation. "
        "Ne pas utiliser pour : une simple note (crm.lead.note) ni clore "
        "une touche (crm.suivi.proposer_reponse). "
        "Exemple : « Note que je l'ai appelé, il rappellera lundi ». "
        "Résultat : l'entrée du fil."
    ),
    endpoint='/api/django/crm/leads/{id}/log-interaction/',
    method='POST',
    inputs=_entrees_journaliser(),
    required_permission='crm_modifier',
    risk=RISK_OUTWARD,
    lot=LOT_COPILOTE,
    objets={'id': 'lead'},
)

PLANIFIER_VISITE = AgentAction(
    key='crm.visite.planifier',
    label='Planifier une visite',
    description=(
        "Sert à : poser la visite technique d'un lead (date, touche qui "
        "l'a demandée) ; le technicien est notifié, après confirmation. "
        "Ne pas utiliser pour : une visite de maintenance "
        "(installations) ni proposer la visite (crm.visite.message). "
        "Exemple : « Il est d'accord pour une visite samedi ». "
        "Résultat : {visite, prochaine_touche}."
    ),
    endpoint='/api/django/crm/leads/{id}/visites/planifier/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'date_prevue': {'type': 'string', 'format': 'date',
                            'description': 'AAAA-MM-JJ, pas dans le passé.'},
            'etape': {'type': 'integer',
                      'description': 'touche_id qui demande la visite.'},
            'notes': {'type': 'string'},
            'note_etape': {'type': 'string'},
            'replanifier': {'type': 'boolean',
                            'description': 'Déplacer le rendez-vous en attente.'},
        },
        'required': ['id', 'date_prevue'],
    },
    required_permission='crm_modifier',
    risk=RISK_OUTWARD,
    carte='visite',
    lot=LOT_COPILOTE,
    objets={'id': 'lead', 'etape': 'touche'},
)

MESSAGE_VISITE = AgentAction(
    key='crm.visite.message',
    label='Message de visite',
    description=(
        "Sert à : préparer le message VALIDÉ pour proposer ou confirmer la "
        "visite technique (texte du serveur, une langue). Rien n'est "
        "envoyé. "
        "Ne pas utiliser pour : planifier la visite (crm.visite.planifier). "
        "Exemple : « Prépare la confirmation de visite pour le lead 12 ». "
        "Résultat : {texte, wa_url, modele_source, langue_servie}."
    ),
    endpoint='/api/django/crm/assistant/leads/{id}/message-visite/',
    method='GET',
    inputs=_entrees_message_visite(),
    required_permission='crm_voir',
    risk=RISK_INTERNAL,
    carte='wa_message',
    lot=LOT_COPILOTE,
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
    CHERCHER_LEAD,
    PREPARER_TOUCHE,
    PROPOSER_REPONSE,
    QUALIFIER_LEAD,
    CHANGER_ETAPE_LEAD,
    JOURNALISER_LEAD,
    PLANIFIER_VISITE,
    MESSAGE_VISITE,
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
