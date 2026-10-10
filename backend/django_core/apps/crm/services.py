"""QJ6 + Lead → Client resolution.

QJ6 — recompute_lead_score(lead) persiste le score calculé sur le lead pour
permettre un tri pagination-safe (?ordering=-score). Appelé dans perform_create
et perform_update du LeadViewSet.

Lead → Client resolution (approach approved by the founder, 2026-06-12).

A quote always carries a Client; when it starts from a Lead the client is
resolved automatically, without ever creating duplicates:

  1. the lead is already linked to a client  → reuse that client;
  2. the lead has an email matching an existing client of the SAME company
     (case-insensitive)                      → link and reuse that client;
  3. otherwise                               → create a client from the lead's
     contact details and link it.

The resolved link is persisted on the lead, so every later quote from the
same lead reuses the same client. Everything stays tenant-scoped.
"""
import logging

from rest_framework.exceptions import ValidationError as DRFValidationError

# CRX26 — LA date MÉTIER (Africa/Casablanca), lue EXPLICITEMENT : elle ne dépend
# d'aucun réglage global. Avant AUD836, ``settings.TIME_ZONE`` valait ``'UTC'``
# et ``timezone.localdate()`` était en retard d'un jour entier une heure par
# nuit ; le réglage dit désormais la même chose, ce helper reste la garantie.


from . import activity, stages
from .models import Lead, LeadActivity

from .leads_socle import (  # noqa: F401 — façade
    _company_fallback_managers,
    lead_notification_recipients,
    motif_refus_valide,
    user_and_superior_recipients,
    visite_point_eau_requise,
    visite_pro_avant_devis,
)

from .leads_doublons import find_duplicates_by_contact, normalize_phone
from .leads_doublons import is_strong_identity_match, normalize_email  # noqa: F401 — façade

from .leads_attribution import default_responsable_for

from .leads_premier_contact import maybe_set_first_contacted_at

from .leads_consentement import (
    BASE_LEGALE_NON_COLLECTEE,
    CONSENT_SOURCE_DOCUMENT,
    enregistrer_base_legale_lead,
)
from .leads_consentement import enregistrer_consentements_intake_web  # noqa: F401 — façade

from .visites_rdv import public_booking_url, send_due_appointment_reminders  # noqa: F401 — façade

from .visites_retour_lead import journaliser_visite  # noqa: F401 — façade


from .cadence_messages import (  # noqa: F401 — façade
    _corps_pour_segment,
    _omettre_phrases_incompletes,
    message_pour_etape,
)

from .fiche_funnel import (
    _STAGE_CONTACTED,
    _bulk_stage_allowed,
    _emit_stage_changed,
    _rang_funnel,
    appliquer_stage_lead,
)
from .fiche_funnel import (  # noqa: F401 — façade
    ajuster_score_lead,
    assigner_lead_a,
    avancer_stage_lead_vers,
    creer_relance_lead,
    poser_tag_lead,
    retirer_tag_lead,
)

from .cadence_plan import demarrer_cadence_contact, sync_relance_activity
from .cadence_plan import (  # noqa: F401 — façade
    _garde_cadence_contact,
    arreter_cadence,
    calculer_echeances_cadence,
    devis_envoyes_pour_relance,
)


from .cadence_touche import reprendre_cadence_apres_reouverture

from .clients_identite import _email_identite
from .clients_identite import (  # noqa: F401 — façade
    clients_par_ids,
    completer_client_depuis_acceptation,
    ecrire_identite_client,
    merge_clients,
    resolve_client_for_lead,
)

from .leads_score import recompute_lead_score
from .leads_score import maybe_assign_mql  # noqa: F401 — façade

from .leads_notifications import notify_new_lead
from .leads_notifications import notify_devis_opened  # noqa: F401 — façade

from .cadence_signaux import (  # noqa: F401 — façade
    CALLBACK_REQUESTED_MARKER,
    SIGNAL_PROPOSITION_ROUVERTE,
    noter_version_remplacee_ouverte,
    notifier_signal_lecture,
    notify_client_contact_request,
    notify_lead_callback_requested,
    poser_touche_signal_du_lead_id,
)

from .devis_chatter import (  # noqa: F401 — façade
    noter_devis_corrige,
    noter_devis_envoye,
    noter_devis_ouvert,
    noter_devis_reouvert,
)

from .clients_pilotage import (  # noqa: F401 — façade
    ajouter_specialite_partenaire,
    handle_parrainage_signup,
    poser_compteur_deploiements,
    soumettre_lead_partenaire,
)

from .fiche_ecritures import (  # noqa: F401 — façade
    CHAMP_AUTO_CADENCE,
    CHAMP_AUTO_INCHANGE,
    CHAMP_AUTO_INVALIDE,
    appliquer_champ_automatique,
    noter_touche_marketing,
)

from .fiche_archivage import delete_leads_for_company  # noqa: F401 — façade

from .leads_meta import (  # noqa: F401 — façade
    _apply_meta_form_extras,
    _meta_type_installation,
    _parse_meta_form_extras,
    backfill_meta_lead_attribution,
    create_lead_from_meta_lead_ads,
    create_minimal_lead_from_ctwa,
    fetch_meta_lead_node,
    import_external_notes_for_contact,
)

# T-TRACE — le traçage des visiteurs externes vit dans son propre module
# (``apps/crm/visites.py``) pour ne pas gonfler ce fichier déjà très long,
# mais il est RÉEXPORTÉ ici : `services` reste la porte d'entrée unique des
# écritures CRM (les accroches n'importent jamais `visites` directement).
from .visites import (  # noqa: F401 — réexport public délibéré
    COOKIE_APPAREIL,
    COOKIE_EQUIPE,
    alerter_appareil_partage,
    appareil_de_requete,
    appareils_equipe_ids,
    avec_direction,
    detecter_concurrent,
    domaine_cookies_equipe,
    enregistrer_appareil_equipe,
    enregistrer_visite_externe,
    est_appareil_equipe,
    historique_appareil,
    ip_de_requete,
    rattacher_visites_au_lead,
    requete_marquee_equipe,
    resume_historique_fr,
    tracer_et_correler,
    user_agent_de_requete,
    utilisateurs_direction,
)

logger = logging.getLogger(__name__)


# ── YLEAD11 — Réactivation d'un lead perdu/COLD sur nouvelle touche entrante ──

def reactivate_lead_on_new_touch(lead, *, source='site web') -> bool:
    """YLEAD11 — Réactive ``lead`` s'il est actuellement PERDU ou COLD.

    Une nouvelle touche entrante (re-POST site web, nouveau message WhatsApp)
    sur un lead perdu/froid rouvre le cycle d'achat : lève ``perdu``,
    repositionne le funnel (AVANCE-SEULEMENT, jamais en arrière — donc un
    lead déjà ≥ CONTACTED et non perdu ne bouge pas) vers CONTACTED s'il
    avait déjà été contacté (``first_contacted_at`` posé), sinon NEW, et
    journalise une activité de réactivation. N'écrase JAMAIS l'attribution
    first-touch d'origine (ce service ne touche à aucun champ UTM/fbclid).
    Idempotent : un lead ni perdu ni COLD → no-op (False). Company-scopée par
    construction (opère sur l'instance ``lead`` déjà résolue dans SA société).
    """
    if lead is None:
        return False
    etait_perdu = bool(lead.perdu)
    etait_cold = lead.stage == stages.COLD
    if not etait_perdu and not etait_cold:
        return False

    if etait_perdu:
        lead.perdu = False
        lead.save(update_fields=['perdu'])

    cible = _STAGE_CONTACTED if lead.first_contacted_at else stages.NEW
    ancien_stage = None  # étape déjà ≥ cible — pas de changement d'étape.
    if _rang_funnel(lead.stage) < _rang_funnel(cible):
        etape_avant = lead.stage
        # ALEA2 — sortie du Froid/Perdu par le point de passage CANONIQUE
        # (CRX20) : écrit l'étape et émet `lead_stage_changed`.
        if appliquer_stage_lead(lead, cible):
            ancien_stage = etape_avant

    # ALEA2 — libellé lisible au chatter : « Nouvelle demande reçue (site
    # web) » / « (WhatsApp) ».
    body = f'auto — réactivation : Nouvelle demande reçue ({source})'
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=body)
    if ancien_stage is not None:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.MODIFICATION,
            field='stage', field_label='Étape',
            old_value=stages.STAGE_LABELS[ancien_stage],
            new_value=stages.STAGE_LABELS[cible],
            body=f'auto — réactivation ({source})',
        )
    # CAD107 — une réouverture pose une CADENCE DE REPRISE, quel que soit le
    # chemin. Best-effort : une nouvelle touche entrante ne doit jamais
    # échouer sur une cadence.
    try:
        reprendre_cadence_apres_reouverture(lead, None, origine=source)
    except Exception:  # noqa: BLE001
        logger.warning(
            'CAD107: reprise non posée après réactivation (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
    return True


# ── ACRM35 — un geste de cadence à la fois par lead ─────────────────────────


# FG28 — SLA première prise de contact ────────────────────────────────────────


# ── CAD-B ── CAD106 ─────────────────────────────────────────────────────────


def create_draft_lead_from_ocr(*, company, user, fields) -> Lead:
    """FG106 — crée un LEAD brouillon à partir de champs extraits par l'OCR.

    Point d'entrée cross-app sanctionné (services.py) pour la passerelle
    OCR → CRM (apps.publicapi). La société vient TOUJOURS du serveur (jamais du
    corps), l'attribution du propriétaire suit la même règle que la création
    normale d'un lead, et la création est tracée dans le chatter. ``fields`` est
    le dict de données structurées OCR ; seuls des champs sûrs y sont lus —
    aucune confiance n'est accordée à des clés inattendues.

    Le lead reste à l'étape par défaut (NEW) : ce service CRÉE, il ne fait pas
    avancer le funnel.
    """
    fields = fields or {}
    nom = (fields.get('fournisseur') or fields.get('client') or '').strip()
    if not nom:
        raise ValueError("Aucun nom de fournisseur/client exploitable dans le document.")

    extra = {}
    # Même règle d'attribution que LeadViewSet.perform_create : un compte à
    # portée restreinte garde la propriété de ce qu'il crée.
    if user is not None and getattr(user, 'record_scope', None) and \
            user.record_scope() != 'all':
        extra['owner'] = user
    else:
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default

    lead = Lead.objects.create(
        company=company,
        nom=nom[:255],
        source=Lead.Source.OS_NATIVE,
        canal=Lead.Canal.AUTRE,
        **extra,
    )
    activity.log_creation(lead, user)
    # Note SYSTÈME (user=None) : annotation automatique, pas un contact manuel —
    # sinon le récepteur QJ7 ferait avancer le lead NEW → CONTACTED alors que ce
    # service CRÉE seulement et laisse le funnel à l'étape par défaut (NEW).
    activity.log_note(
        lead, None,
        "Lead créé depuis un document OCR (brouillon à compléter).")
    # CAD90 — données lues sur un document, jamais collectées auprès de la
    # personne par nous : c'est l'art. 5 §3 qui s'applique, et le registre
    # doit le dire au lieu de rester muet.
    enregistrer_base_legale_lead(
        lead, source=CONSENT_SOURCE_DOCUMENT,
        base_legale=BASE_LEGALE_NON_COLLECTEE)
    recompute_lead_score(lead)
    return lead


# ── XSAL8 — Scan de carte de visite (salon/chantier) → pré-remplissage ──────
#
# NE crée JAMAIS de lead : lit une photo, l'envoie à l'OCR EXISTANT
# (``core.ai.services.extract_document``, gabarit ``carte_visite`` — la même
# capacité que FG355/XRH23, key-gated ZHIPU_API_KEY, NO-OP-safe), et renvoie
# les champs reconnus pour PRÉ-REMPLIR le modal « Lead express » — la création
# reste TOUJOURS un geste explicite de l'utilisateur (bouton « Créer »).

# Mêmes octets magiques que ``apps.records.storage`` (jamais de nouvelle
# dépendance) : la carte de visite est une simple PHOTO (JPEG/PNG/WebP),
# jamais un PDF.
_CARTE_VISITE_MAX_BYTES = 8 * 1024 * 1024  # 8 Mo (photo mobile courante)
_CARTE_VISITE_MAGIC = {
    'image/png': lambda h: h[:8] == b'\x89PNG\r\n\x1a\n',
    'image/jpeg': lambda h: h[:3] == b'\xff\xd8\xff',
    'image/webp': lambda h: h[:4] == b'RIFF' and h[8:12] == b'WEBP',
}


class CarteVisiteScanUnavailable(Exception):
    """XSAL8 — levée quand l'OCR n'est pas configuré (503 douce côté vue) ou
    quand le fichier fourni n'est pas une image reconnue (400 côté vue)."""


def scan_carte_visite(*, company, file_bytes, mime_hint='', queryset=None):
    """XSAL8 — Extrait nom/société/téléphone/email d'une photo de carte de
    visite, PRÉ-VÉRIFIE les doublons, et renvoie un dict prêt à pré-remplir le
    modal « Lead express » — NE CRÉE JAMAIS de lead (l'utilisateur valide).

    Lève :class:`CarteVisiteScanUnavailable` si le fichier n'est pas une image
    reconnue (magic bytes) OU trop volumineux OU si aucun fournisseur OCR
    n'est configuré (``ZHIPU_API_KEY`` absent — dégradation propre, jamais
    d'appel réseau). Ne persiste JAMAIS l'image reçue au-delà du traitement en
    mémoire (aucun stockage MinIO — contrairement aux autres flux OCR qui
    rattachent le fichier en pièce jointe).

    ACRM7 (jumeau) — ``queryset`` borne la pré-vérification des doublons aux
    leads de la PORTÉE de l'appelant (``None`` = toute la société)."""
    if not file_bytes:
        raise CarteVisiteScanUnavailable('Aucune image fournie.')
    if len(file_bytes) > _CARTE_VISITE_MAX_BYTES:
        raise CarteVisiteScanUnavailable('Image trop volumineuse (max 8 Mo).')

    header = file_bytes[:12]
    mime = None
    for candidate_mime, test in _CARTE_VISITE_MAGIC.items():
        if test(header):
            mime = candidate_mime
            break
    if mime is None:
        raise CarteVisiteScanUnavailable(
            'Format non reconnu (JPEG, PNG ou WebP uniquement).')

    from core.ai.services import extract_document
    result = extract_document(
        content=file_bytes, mime_type=mime, schema='carte_visite')
    if not result.configured:
        raise CarteVisiteScanUnavailable(
            "Aucun fournisseur OCR n'est configuré (clé absente) — "
            'saisie manuelle requise.')

    data = result.data or {}
    nom = str(data.get('nom') or '').strip()[:255]
    prenom = str(data.get('prenom') or '').strip()[:255]
    societe = str(data.get('societe') or '').strip()[:255]
    telephone = str(data.get('telephone') or '').strip()[:50]
    email = str(data.get('email') or '').strip()[:254]

    doublons = []
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None,
            queryset=queryset)
        doublons = [
            {'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
             'telephone': d.telephone, 'email': d.email}
            for d in dupes
        ]

    return {
        'nom': nom, 'prenom': prenom, 'societe': societe,
        'telephone': telephone, 'email': email,
        'doublons': doublons,
    }


# ── YLEAD8 — Rattacher l'inbound WhatsApp à un lead OUVERT existant ──────────

def resolve_or_create_lead_from_whatsapp(company, telephone, nom='',
                                         user=None) -> Lead:
    """YLEAD8 — Réutilise un lead OUVERT existant (même téléphone) au lieu de
    toujours créer un doublon sur un message WhatsApp entrant.

    « Ouvert » = non perdu (``Lead.perdu`` False) et non archivé
    (``archived_at`` NULL). Parmi les leads ouverts partageant ce téléphone,
    prend le plus récent ; journalise le message inbound dans SON chatter.

    YLEAD11 — si aucun lead OUVERT n'existe mais qu'un lead PERDU/COLD (non
    archivé) partage ce téléphone, il est RÉACTIVÉ (même règle que le
    webhook site : lève ``perdu``, repositionne NEW/CONTACTED avance-seul)
    plutôt que de créer un doublon — une nouvelle touche WhatsApp rouvre
    aussi le cycle d'achat.

    N'appelle ``create_draft_lead_from_ocr`` qu'en DERNIER RECOURS (aucun
    lead — ouvert ou réactivable — trouvé pour ce numéro) — c'est ce service
    qui doit être appelé par ``compta.services.capturer_message_whatsapp``,
    jamais l'inverse. Company-scopé ; gated en amont par l'appelant (NO-OP si
    WhatsApp OFF).
    """
    candidates = find_duplicates_by_contact(company, phone=telephone)
    non_archives = [c for c in candidates if c.archived_at is None]
    # ALEA2 — un lead au Froid (non perdu) n'est PAS « ouvert » : il est
    # réactivable, comme le perdu (alignement sur le webhook du site).
    ouverts = [lead_ for lead_ in non_archives
               if not lead_.perdu and lead_.stage != stages.COLD]
    if ouverts:
        lead = sorted(ouverts, key=lambda d: d.date_creation, reverse=True)[0]
        body = 'Nouveau message WhatsApp reçu'
        if nom:
            body += f' de {nom}'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE, body=body)
        return lead

    # YLEAD11 — aucun lead ouvert : un lead perdu/COLD non archivé est
    # réactivé plutôt que dupliqué.
    reactivables = [lead_ for lead_ in non_archives
                    if lead_.perdu or lead_.stage == stages.COLD]
    if reactivables:
        lead = sorted(
            reactivables, key=lambda d: d.date_creation, reverse=True)[0]
        reactivate_lead_on_new_touch(lead, source='WhatsApp')
        return lead

    lead = create_draft_lead_from_ocr(
        company=company, user=user,
        fields={'client': nom or telephone})
    # create_draft_lead_from_ocr ne lit que fournisseur/client (nom) — le
    # téléphone/whatsapp est posé ICI pour que le PROCHAIN message du même
    # numéro retrouve ce lead via find_duplicates_by_contact (sinon YLEAD8
    # créerait un doublon à chaque message, ce que ce service existe pour
    # éviter). BUG RÉEL corrigé ici : Lead.save() recalcule
    # phone_normalise/email_normalise EN MÉMOIRE à chaque save() (avant
    # super().save()), mais save(update_fields=[...]) ne PERSISTE que les
    # colonnes listées — sans 'phone_normalise' ici, la colonne restait ''
    # en base malgré le téléphone posé, et find_duplicates_by_contact (qui
    # filtre sur phone_normalise) ne retrouvait jamais ce lead au message
    # suivant : chaque nouveau message du même numéro créait un DOUBLON.
    if telephone:
        lead.telephone = telephone
        lead.whatsapp = telephone
        lead.save(update_fields=['telephone', 'whatsapp', 'phone_normalise',
                                 'whatsapp_normalise'])
    return lead


# ── XMKT32 — Sync Meta Lead Ads → leads CRM (gated) ───────────────────────────


# ── XMKT37 — Livechat / assistant IA de qualification (ERP-side) ─────────────

def create_lead_from_livechat(*, company, nom, telephone='', email='',
                              transcript_text='') -> Lead:
    """XMKT37 — Crée (ou dédupe sur) un lead dès que nom + contact sont captés
    par une session de livechat public.

    Point d'entrée cross-app sanctionné (services.py), appelé par
    ``apps.crm.public_chat_views``. Dédup (QJ8) par téléphone/email dans la
    société avant de créer (comme le webhook site) ; canal ``livechat``,
    stage NEW (STAGES.py, jamais hardcodé — ``Lead.stage`` a NEW pour
    défaut). Le transcript complet est collé en note chatter (``LeadActivity``).
    """
    nom = (nom or '').strip()[:255] or 'Prospect livechat'
    telephone = (telephone or '').strip()[:20]
    email = (email or '').strip()[:254]

    lead = None
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)
        if dupes:
            lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    if lead is None:
        extra = {}
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default
        lead = Lead.objects.create(
            company=company,
            nom=nom,
            telephone=telephone or None,
            email=email or None,
            canal=Lead.Canal.AUTRE,
            **extra,
        )
        activity.log_creation(lead, None)
        try:
            notify_new_lead(lead)
        except Exception:  # noqa: BLE001 — best-effort
            pass
        # MRY6 — même démarrage explicite que les autres créateurs vivants.
        demarrer_cadence_contact(lead, origine='livechat')
    else:
        changed = False
        if telephone and not lead.telephone:
            lead.telephone = telephone
            changed = True
        if email and not lead.email:
            lead.email = email
            changed = True
        if changed:
            lead.save()

    if transcript_text:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=f'Transcript livechat :\n{transcript_text}')

    recompute_lead_score(lead)
    return lead


# ── YLEAD10 — Fast-lane comportemental : FOLLOW_UP à l'ouverture du devis ────


# ── QJ2 — Speed-to-lead : notifications vendeur avec lien wa.me ──────────────


# ── CAD-K ── CAD135 — les signaux de lecture remontent au LEAD ──────────────
#
# Audit L3 du 21/09/2026. Quand un client revient plusieurs fois sur la même
# section (le prix, l'étude), le système écrit lui-même « signal de friction,
# un appel peut débloquer la décision » — dans l'historique du DEVIS, sans
# aucune notification. Même sort pour « a commencé à lire en détail ».
# Personne ne les lit, sauf à ouvrir cet onglet par hasard.
#
# Ces deux signaux empruntent désormais le MÊME chemin que « devis ouvert » :
# une ligne dans le chatter du LEAD et une notification au responsable, avec
# le lien pour appeler. La note côté DEVIS reste écrite — elle appartient à
# l'historique du document, ce point d'entrée ne la remplace pas.
#
# NUANCE ASSUMÉE (round 2) : « le signal le plus prédictif » reste une
# HYPOTHÈSE tant que CAD87 ne l'a pas mesuré. Rien ici ne classe, ne priorise
# ni ne réordonne quoi que ce soit : on rend un fait visible, c'est tout.


# ─────────────────────────────────────────────────────────────────────────────
# Actions EN MASSE sur les leads (T3) — multi-sélection liste/kanban.
#
# Toute la logique métier vit ici (les vues restent fines) : règles du funnel
# (jamais en arrière, jamais un lead Perdu, réactivation du Froid), journal
# Historique par lead marqué « en masse », et garde-fous (devis liés bloquent la
# suppression). Tout est borné à la société de l'utilisateur appelant.
# ─────────────────────────────────────────────────────────────────────────────


# ── QJ20 — Site-visit appointment service ────────────────────────────────────


# ── XKB33 — WhatsApp entrant → chatter du lead/client ────────────────────────

def find_lead_by_phone(company, telephone):
    """Lead de `company` dont téléphone OU whatsapp correspond (normalisé).

    Point d'entrée cross-app sanctionné pour `apps.notifications` (webhook BSP
    WhatsApp) : matching par numéro SANS jamais exposer les modèles crm.
    Renvoie le lead le plus RÉCEMMENT créé en cas de doublon, ou None."""
    key = normalize_phone(telephone)
    if not key:
        return None
    candidates = [
        lead for lead in Lead.objects.filter(company=company)
        .order_by('-date_creation')
        if normalize_phone(lead.telephone) == key
        or normalize_phone(lead.whatsapp) == key
    ]
    return candidates[0] if candidates else None


def find_lead_by_email(company, email):
    """NTAPI15 — Lead de `company` dont l'email correspond (insensible à la
    casse). Point d'entrée cross-app sanctionné pour `apps.publicapi` (dédup
    upsert de l'import bulk) — jamais d'import direct de `Lead` ailleurs.
    Renvoie le lead le plus RÉCEMMENT créé en cas de doublon, ou None."""
    # ACRM38 (jumeau) — la même clé que l'identité client.
    email = _email_identite(email)
    if not email:
        return None
    return (
        Lead.objects.filter(company=company, email__iexact=email)
        .order_by('-date_creation')
        .first()
    )


# ── ZSAV8 — Convertir un ticket SAV en opportunité CRM ──────────────────────
# apps.sav ne peut PAS importer apps.crm.models directement (règle de
# modularité CLAUDE.md) : cette fonction est son unique porte d'entrée pour
# créer un lead depuis un ticket (upsell/remplacement).

def create_lead_depuis_ticket(*, company, user, client, contexte=''):
    """ZSAV8 — Crée (ou réutilise) un lead CRM depuis un ticket SAV.

    Réutilise un lead OUVERT (stage != COLD, non archivé) déjà lié à ce
    ``client`` plutôt que d'en créer un doublon. Sinon, crée un nouveau lead
    au stade ``NEW`` (STAGES.py, jamais codé en dur), pré-rempli avec
    l'identité du client + ``contexte`` en description.

    La note de ``contexte`` est attribuée au SYSTÈME (``user=None``) et non à
    l'utilisateur appelant : le récepteur QJ7
    (``_avancer_stage_on_contact_activity``) ne fait avancer NEW -> CONTACTED
    que sur un premier contact MANUEL (``instance.user is not None``), donc une
    note système laisse le lead au stade ``NEW`` attendu par ZSAV8 tout en
    conservant la trace « Créé depuis le ticket SAV … » sur le chatter du lead.

    Renvoie ``(lead, created)``."""
    # ACRM43 — la docstring dit « non archivé » : un lead archivé n'est
    # jamais réutilisé (nouveau lead à la place).
    existant = (
        Lead.objects
        .filter(company=company, client=client, is_archived=False)
        .exclude(stage=stages.COLD)
        .order_by('-date_creation')
        .first())
    if existant is not None:
        contexte_existant = (contexte or '').strip()
        if contexte_existant:
            # ACRM43 — le contexte du ticket est tracé au chatter du lead
            # réutilisé (note SYSTÈME, même règle QJ7 que la création).
            activity.log_note(existant, None, contexte_existant)
        return existant, False

    lead = Lead.objects.create(
        company=company,
        nom=f'{client.nom} {client.prenom or ""}'.strip() or client.nom,
        prenom=client.prenom or None,
        email=client.email or None,
        telephone=client.telephone or None,
        client=client,
        canal=Lead.Canal.AUTRE,
        stage=stages.NEW,
    )
    activity.log_creation(lead, user)
    contexte = (contexte or '').strip()
    if contexte:
        # Note SYSTÈME (user=None) : garde le lead au stade NEW (le récepteur
        # QJ7 ignore les activités système), tout en traçant l'origine.
        activity.log_note(lead, None, contexte)
    return lead, True


# ── XMKT4 — écriture de consentement marketing pour un lead ────────────────
# Point d'entrée UNIQUE pour poser un ``core.ConsentRecord`` depuis un lead
# (jamais d'écriture directe de compta/parametres dans core.ConsentRecord au
# nom d'un lead — cette fonction reste la porte d'entrée crm).


# ── XMKT19 — Actions CRM exécutables depuis une étape de séquence ──────────
# Point d'entrée UNIQUE pour qu'une ``EtapeSequence`` (module marketing de
# compta) exécute une action CRM au lieu d'un message — jamais d'import
# direct du modèle crm depuis compta ; chaque fonction journalise le chatter
# (``LeadActivity``) via ``activity``, jamais silencieuse.


# ── XMKT28 — Lead depuis une inscription à un événement marketing ──────────

def create_lead_from_evenement_marketing(
        *, company, nom, telephone='', email='', evenement_nom='') -> Lead:
    """XMKT28 — Crée (ou dédupe sur) un lead dès qu'un inscrit à un
    ``EvenementMarketing`` (module marketing de compta) est capturé. Même
    pattern que ``create_lead_from_livechat`` (XMKT37) : dédup par
    téléphone/email dans la société avant de créer, canal ``AUTRE``, stage
    NEW (défaut du champ).
    """
    nom = (nom or '').strip()[:255] or 'Prospect événement'
    telephone = (telephone or '').strip()[:20]
    email = (email or '').strip()[:254]

    lead = None
    if telephone or email:
        dupes = find_duplicates_by_contact(
            company, phone=telephone or None, email=email or None)
        if dupes:
            lead = sorted(dupes, key=lambda d: d.date_creation, reverse=True)[0]

    if lead is None:
        extra = {}
        default = default_responsable_for(company)
        if default is not None:
            extra['owner'] = default
        lead = Lead.objects.create(
            company=company,
            nom=nom,
            telephone=telephone or None,
            email=email or None,
            canal=Lead.Canal.AUTRE,
            **extra,
        )
        activity.log_creation(lead, None)
        # MRY6 — un inscrit d'événement marketing est une demande réelle.
        demarrer_cadence_contact(lead, origine='evenement_marketing')
    else:
        changed = False
        if telephone and not lead.telephone:
            lead.telephone = telephone
            changed = True
        if email and not lead.email:
            lead.email = email
            changed = True
        if changed:
            lead.save()

    if evenement_nom:
        activity.log_note(
            lead, None, f'Inscrit à l\'événement « {evenement_nom} »')
    recompute_lead_score(lead)
    return lead


# ── XPLT5 — API publique en ÉCRITURE (leads:write / activities:write) ───────
# Point d'entrée cross-app sanctionné (services.py) pour `apps.publicapi` :
# la société vient TOUJOURS de l'appelant (résolue depuis la clé API, jamais
# du corps), jamais acceptée en argument depuis les données utilisateur.

PUBLIC_LEAD_WRITABLE_FIELDS = (
    'nom', 'prenom', 'societe', 'email', 'telephone', 'ville',
    'canal', 'priorite', 'type_installation', 'stage',
)


def create_lead_from_public_api(*, company, fields):
    """XPLT5 — crée un lead depuis l'API publique en écriture.

    ``fields`` est filtré à la liste blanche ``PUBLIC_LEAD_WRITABLE_FIELDS``
    (un champ non listé est silencieusement ignoré — jamais 500). ``stage``,
    s'il est fourni, doit être une clé canonique STAGES.py valide (sinon
    ``ValueError`` — jamais de nouvelle liste d'étapes, jamais hardcodée) ;
    absent, le lead prend le défaut du modèle (NEW). ``nom`` est obligatoire.
    Company forcée serveur, jamais du body. Journalise la création
    (``LeadActivity``, acteur système) comme tout autre point d'entrée."""
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS and v not in (None, '')}
    nom = (clean.pop('nom', '') or '').strip()
    if not nom:
        raise ValueError("Le champ « nom » est obligatoire.")
    stage = clean.pop('stage', None)
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    lead = Lead.objects.create(
        company=company, nom=nom,
        stage=stage or stages.NEW,
        **clean,
    )
    activity.log_creation(lead, None)
    # MRY6 — l'API publique crée de VRAIES demandes (formulaire partenaire,
    # intégration) : elles entrent dans la cadence comme les autres.
    demarrer_cadence_contact(lead, origine='api_publique')
    return lead


#: CRX21 — colonnes DÉRIVÉES recalculées par ``Lead.save()`` (QW10). Sans
#: elles dans ``update_fields``, un changement de téléphone/email n'est PAS
#: répercuté sur les colonnes indexées de dédup : le lead reste trouvable par
#: son ANCIEN numéro et invisible sous le nouveau. Même table que
#: ``LeadViewSet.COLONNES_DERIVEES`` (views.py) — la parité est le sujet de la
#: tâche : l'API publique écrit les mêmes leads que l'écran.
PUBLIC_LEAD_COLONNES_DERIVEES = {'telephone': 'phone_normalise',
                                 'email': 'email_normalise'}


def update_lead_from_public_api(*, company, lead_id, fields):
    """XPLT5 — met à jour un lead EXISTANT DE CETTE SOCIÉTÉ depuis l'API
    publique en écriture. Lève ``Lead.DoesNotExist`` si le lead n'appartient
    pas (ou plus) à ``company`` — jamais de fuite cross-tenant. Champs
    filtrés à la même liste blanche que la création ; ``stage`` validé contre
    STAGES.py. Journalise chaque champ changé (chatter, acteur système).

    CRX21 — PARITÉ avec le PATCH de l'écran (``LeadViewSet.perform_update``),
    qui manquait entièrement à ce chemin :

    * **verrou du lead perdu** — un lead marqué perdu ne change pas d'étape,
      pas même par une intégration (le ``LeadSerializer`` refuse déjà, et ce
      verrou PRÉCÈDE toute échappatoire) ;
    * **garde funnel** ``_bulk_stage_allowed`` — une intégration ne recule ni
      ne rouvre un pipeline. Il n'y a PAS ici l'échappatoire ``confirme_recul``
      de l'écran : elle suppose une confirmation HUMAINE devant un lead nommé,
      qu'aucun appel machine ne peut donner ;
    * **les 4 effets internes** de ``perform_update`` : émission de
      ``lead_stage_changed``, ``first_contacted_at`` (FG28), recalcul du score
      (QJ6) et synchronisation de l'activité de relance ;
    * **colonnes dérivées** (``phone_normalise``/``email_normalise``) ajoutées
      à ``update_fields`` quand leur source change — sinon la dédup indexée
      devient aveugle après un changement de téléphone (chemins publicapi bulk
      ET PATCH unitaire).

    Lève ``ValueError`` (traduit en 400 par les vues publiques) sur une étape
    inconnue, un lead perdu, ou un recul de funnel.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS}
    stage = clean.get('stage')
    # ACRM58 — ``stage`` présent mais vide (null comme '') : erreur SOUS LE
    # CHAMP (400 ``{stage: [...]}``), jamais un IntegrityError (500). Une
    # ValidationError DRF (pas un ValueError) pour que la vue publique la
    # rende telle quelle, champ nommé ; l'import en masse l'inscrit en ligne
    # en erreur.
    if 'stage' in clean and stage in (None, ''):
        raise DRFValidationError(
            {'stage': ["L'étape ne peut pas être vide."]})
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    if stage is not None and stage != lead.stage:
        if lead.perdu:
            raise ValueError('Lead perdu — étape non modifiable.')
        if not _bulk_stage_allowed(lead.stage, stage):
            raise ValueError("On ne recule pas une étape.")
    old = Lead.objects.get(pk=lead.pk)
    changed_fields = []
    for field, value in clean.items():
        if value in (None, '') and field != 'stage':
            continue
        if getattr(lead, field) != value:
            setattr(lead, field, value)
            changed_fields.append(field)
    if changed_fields:
        ecrits = list(changed_fields)
        for source, derivee in PUBLIC_LEAD_COLONNES_DERIVEES.items():
            if source in changed_fields:
                ecrits.append(derivee)
        lead.save(update_fields=ecrits)
        activity.log_changes(old, lead, None)
        # Les 4 effets du PATCH de l'écran, dans le même ordre. Tous sont
        # best-effort par construction (chacun catche pour son compte) : une
        # intégration ne doit jamais échouer sur un effet secondaire.
        sync_relance_activity(lead, None)
        maybe_set_first_contacted_at(old, lead)
        recompute_lead_score(lead)
        _emit_stage_changed(lead, old.stage, lead.stage, user=None)
    return lead


def create_activity_from_public_api(*, company, lead_id, body):
    """XPLT5 — ajoute une note (activité chatter) sur un lead DE CETTE
    SOCIÉTÉ depuis l'API publique en écriture. Lève ``Lead.DoesNotExist`` si
    hors société (jamais de fuite cross-tenant). ``body`` ne peut être vide."""
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    return activity.log_note(lead, None, body)


def ajouter_note_lead(*, company, lead_id, user, body):
    """NTMOB1 — ajoute une note (activité chatter) sur un lead DE CETTE
    SOCIÉTÉ, avec l'utilisateur ACTEUR (contrairement à
    ``create_activity_from_public_api``, qui journalise sans acteur).

    Point d'entrée cross-app pour rejouer une note posée hors-ligne sans
    importer ``apps.crm.models``/``views``. Lève ``Lead.DoesNotExist`` hors
    société (jamais de fuite cross-tenant) et ``ValueError`` sur un corps vide.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    return activity.log_note(lead, user, body)


def ajouter_note_lead_si_nouvelle(*, company, lead_id, user, body):
    """Comme :func:`ajouter_note_lead`, mais SANS RÉPÉTER un corps identique.

    Rend l'activité créée, ou ``None`` si le lead porte DÉJÀ une note au corps
    exactement identique.

    POURQUOI ELLE EXISTE (F6, 29/08/2026). L'auto-pipeline du tunnel doit
    laisser une trace quand le moteur REFUSE de chiffrer un lead — sans quoi le
    commercial constate seulement que « hier ces leads recevaient un devis ».
    Mais le refus RELÂCHE la marque de dédup (une donnée manquante aujourd'hui
    ne doit pas fermer le lead pour toujours) : chaque nouvelle livraison du
    webhook rejoue donc le même refus, et une note par rejeu ensevelirait
    l'historique du lead sous le même paragraphe. La note est donc posée une
    fois par MOTIF : le motif change ⇒ une nouvelle note ; le motif se répète
    ⇒ silence.

    La comparaison porte sur le CORPS et rien d'autre — c'est lui que le
    commercial lit, et c'est lui qui nomme le champ manquant.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    deja = LeadActivity.objects.filter(
        company=company, lead=lead, kind=LeadActivity.Kind.NOTE,
        body=body).exists()
    if deja:
        return None
    return activity.log_note(lead, user, body)


# CAD72 (21/09/2026) — le SECOND catalogue « parrainage » de YSERV11 a
# disparu d'ici. Un dictionnaire de textes par défaut + un générateur
# `get_or_create_*` vivaient ici, semant une SECONDE ligne
# `crm.MessageTemplate` au premier usage — texte FR promettant une
# récompense FERME, et texte darija TRANSCRIT EN ALPHABET LATIN (chiffres
# pour des lettres arabes — « 3 »/« 9 »), alors que le catalogue darija
# validé (`parametres.MESSAGE_TEMPLATE_DEFAULTS_DARIJA`) est écrit en
# arabe, relu par un natif le 04/09/2026. Leur seul appelant vivait dans
# `apps/compta/services.py` (flux NPS), retiré quand `compta` a été mis en
# coquille par le drain SOLMVP (`apps/compta/` n'a plus de `services.py`) —
# plus aucun appelant (grep sur tout le backend). Le catalogue UNIQUE pour
# les messages client est désormais `parametres.MessageTemplate` (clé
# `parrainage`, déjà validée dans `docs/crm/messages_meryem.md`, rendue par
# `message_pour_etape` comme n'importe quelle autre touche) — voir
# `tests_cad72_parrainage_catalogue_unique.py`.


# ─────────────────────────────────────────────────────────────────────────────
# QX42 — Rétention PII des copies brutes d'intake (registre YOPSB10, core.retention)
#
# `WebsiteLeadPayload` (PII brute + IP) et `ChatSessionPublique`
# s'accumulaient INDÉFINIMENT. ACRM19 — l'effacement d'un lead
# (`dsr_provider.anonymiser_lead`, DSR ET rétention) caviarde désormais LUI-MÊME
# ces copies brutes : les purges par âge ci-dessous ne sont plus le seul
# rempart, seulement le ménage de fond. Le framework générique existe (`core.retention`)
# mais son registre est VIDE — aucune app n'y enregistre de politique. Ceci
# enregistre la politique CRM (voir `CrmConfig.ready()`), fenêtre par défaut
# 180 jours, override founder via `WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS` /
# `CHAT_SESSION_RETENTION_DAYS` (settings/.env — même patron que les autres
# constantes founder-configurables de ce module, ex.
# `WEBSITE_LEAD_WEBHOOK_SECRET`). 0/négatif désactive la purge (conservation
# illimitée, comportement actuel inchangé).


# ─────────────────────────────────────────────────────────────────────────────
# YOPSB11 — Archivage par lots de `LeadActivity` (chatter à forte croissance)
#
# Le chatter (`LeadActivity`) est append-only et grossit sans borne, alourdissant
# le chemin chaud. `archiver_anciens(now, jours)` DÉPLACE les entrées plus
# vieilles que `jours` vers la table froide `LeadActivityArchive` (par lots de
# 5 000, un commit par lot — jamais de transaction géante) puis les supprime de
# la table vive. Fenêtre par défaut 0 = OFF (aucun archivage, comportement
# inchangé) ; réglage via `CRM_LEADACTIVITY_ARCHIVE_DAYS`. La politique est
# enregistrée dans le registre partagé YOPSB10 depuis `CrmConfig.ready()`.


# ── NTMIG28 — miroir du compteur de déploiements d'un partenaire ────────────


# ---------------------------------------------------------------------------
# AUD518 — Effets de CRÉATION d'un lead importé (dataimport)
# ---------------------------------------------------------------------------


def finaliser_lead_importe(lead, *, user=None, lead_attrs=None):
    """AUD518 — applique à un lead IMPORTÉ les effets de création du chemin
    MANUEL, dont il était intégralement privé.

    ``apps.dataimport`` faisait ``Lead.objects.create(company=…, **f)`` et
    s'arrêtait là : pas d'``owner`` (donc un lead invisible de l'écran « mes
    leads »), aucune ``LeadActivity`` de création (aucune trace, et le sweep
    d'inactivité sans point de départ), ``score`` figé à 0 (donc jamais
    évalué MQL). Ce point d'entrée est le SEUL que ``dataimport`` appelle :
    la frontière cross-app est respectée (aucun import de ``crm.activity`` ni
    du modèle depuis l'app d'import).

    Trois effets, dans l'ordre du chemin manuel
    (``LeadViewSet.perform_create``) :

    1. OWNER — même règle exactement : un utilisateur à portée restreinte
       garde la propriété de ce qu'il crée, sinon le responsable par défaut
       de la société (territoires NTCRM1 puis repli round-robin XSAL11) est
       résolu depuis les attributs de la ligne. Un ``owner`` déjà posé par le
       fichier n'est JAMAIS écrasé.
    2. CHATTER — ``activity.log_creation`` (l'app d'import n'y touche pas
       elle-même).
    3. SCORE — ``recompute_lead_score``, qui évalue aussi le passage MQL
       (``maybe_assign_mql``). Déjà best-effort en interne.

    Renvoie le lead.
    """
    from . import activity

    if not lead.owner_id:
        proprietaire = None
        portee = getattr(user, 'record_scope', None)
        if user is not None and callable(portee) and portee() != 'all':
            proprietaire = user
        else:
            proprietaire = default_responsable_for(
                lead.company, lead_attrs=lead_attrs)
        if proprietaire is not None:
            lead.owner = proprietaire
            lead.save(update_fields=['owner'])

    activity.log_creation(lead, user)
    recompute_lead_score(lead)
    return lead


# ── MRY30 — PLACEMENT DES ANCIENS LEADS DANS LES CADENCES DU MOTEUR ──────────
#
# Le moteur de relances ne démarre que sur les leads qui ARRIVENT. Le
# portefeuille déjà présent — plusieurs centaines de dossiers, dont les 930
# leads du miroir Odoo — resterait donc sans aucune cadence, et le bénéfice
# n'arriverait qu'au fil des semaines. Décision fondateur du 06/09/2026 :
# « tous les anciens leads non Froid sont traités ; le moteur décide à quelle
# étape des six appels chacun se trouve ».
#
# Trois différences assumées avec la reprise MRY23
# (`demarrer_cadences_existantes`, qui reste en place et ne change pas) :
#
#   1. le MIROIR ODOO EST INCLUS. `_garde_cadence_contact` refuse
#      `source == ODOO_IMPORT_TEST` — garde juste pour un démarrage AUTOMATIQUE
#      à la création (elle empêche un import de 930 lignes d'inonder la file),
#      fausse pour un placement DEMANDÉ à la main sur ce même portefeuille.
#      C'est pourquoi ce service appelle `initialiser_plan_relance`
#      directement et JAMAIS `demarrer_cadence_contact` ;
#   2. il n'y a pas de fenêtre d'éligibilité qui laisse des leads de côté :
#      un dossier trop ancien pour être relancé n'est pas ignoré, il est mis
#      en DORMANCE explicite (Froid + étiquette + réveil étalé) ;
#   3. l'aperçu et l'application partagent LE MÊME CALCUL — sans partager
#      les écritures. L'aperçu était une exécution complète dans une
#      transaction annulée : fidèle, mais il matérialisait les touches des
#      277 candidats pour les jeter aussitôt, soit plus de 20 s pendant
#      lesquelles le navigateur abandonnait (deux 499 dans nginx le
#      07/09/2026, sur le clic « Aperçu » du Cockpit). Il est désormais un
#      CALCUL PUR : mêmes décisions, mêmes créneaux, mêmes dates — obtenus
#      par `calculer_echeances_cadence`, la fonction que l'application
#      utilise elle aussi pour créer les touches. Un dry-run qui recalcule
#      « à côté » finit toujours par annoncer autre chose que ce que --apply
#      fait ; partager la FONCTION donne la même garantie que partager
#      l'exécution, pour le prix d'un calcul ;
#   4. l'application se fait PAR LOTS de `limite` leads (défaut 40), l'écran
#      rappelant tant que `restants > 0`. Écrire 277 dossiers d'un trait
#      dépassait le délai du navigateur exactement comme l'aperçu.


# ── VISITE-CADENCE — LE SUIVI COMMERCIAL RÉAGIT À LA VISITE ──────────────────
#
# Ordre fondateur du 15/09/2026. La visite technique se place APRÈS l'envoi du
# devis, comme outil de closing. Trois conséquences, et elles vivent ICI (pas
# dans les récepteurs, qui restent minces et se contentent d'appeler) :
#
#   * quand un RENDEZ-VOUS est pris, les messages génériques de relance se
#     TAISENT jusqu'après la visite — continuer à demander « le PDF s'ouvre
#     bien ? » à quelqu'un qui reçoit le technicien jeudi est le genre de
#     faute qui décrédibilise tout le suivi — et deux gestes utiles les
#     remplacent en attendant ;
#
#     AMENDEMENT FONDATEUR (15/09/2026) — ils se TAISENT, ils ne MEURENT PAS.
#     La première écriture de ce lot ANNULAIT la cadence après-devis : le lead
#     perdait sa place dans le protocole, et une visite qui n'aboutit pas
#     laissait un dossier sans suivi (ou, pire, exigeait un REDÉMARRAGE de
#     cadence — un client reprenant le plan au barreau 1 après avoir déjà reçu
#     neuf messages). On DÉCALE désormais : la touche pendante, tout ce qui la
#     suit, ET l'ancre de la cadence glissent jusqu'après le débrief. Le lead
#     garde sa POSITION EXACTE (même ordre, même libellé, même reste de plan) ;
#     si la visite ne donne rien, le suivi reprend tout seul là où il en était.
#     Aucun `initialiser_plan_relance` n'est appelé sur un lead qui a déjà des
#     étapes après-devis : il n'y a JAMAIS de restart.
#   * quand le technicien repart, le RESPONSABLE doit rappeler sous 24-48 h,
#     tant que la visite est fraîche ;
#   * le TEXTE LIBRE du terrain entre dans l'historique du lead : c'est
#     souvent la seule trace de ce que le client a dit sur place.
#
# Aucune de ces fonctions ne touche ``Lead.stage`` : le statut d'une visite est
# un layer DOCUMENT, jamais une étape de funnel (``STAGES.py`` intact).


# ── VT1 — CHATTER AUTOMATIQUE DE LA VISITE TECHNIQUE TERRAIN ─────────────────
#
# Le chatter du lead (``LeadActivity``) est le journal COMMUN de tout ce qui
# arrive à un lead : la visite technique y écrit ses quatre moments — création,
# terminaison, feu vert, renvoi — plutôt que d'ouvrir un second historique.
# L'auteur et la société viennent TOUJOURS du serveur (jamais du corps de
# requête), comme le reste du chatter.


# ── AGR522 — DOSSIER DE SUBVENTION FDA : LE RAPPEL DES 3 MOIS ───────────────
#
# Guide FDA 2024 (p.22-23, tableau « Délais ») : « Demande de subvention —
# 3 mois à compter de la date de l'approbation préalable », après la
# RÉALISATION. Au passage à « accordé », une étape MANUELLE datée est posée
# pour le lendemain (filet hors gabarit — jamais une touche de cadence,
# CAD124). Ce délai n'est JAMAIS écrit au client.


# ── NTDATA18 — FUSION SUPERVISÉE DE CLIENTS ─────────────────────────────────
#
# Sur le modèle de `merge_leads` ci-dessus, mais pour `Client` : le détecteur
# (`dataquality.services.doublons_clients`) PROPOSE, un humain DÉCIDE, et cette
# fonction exécute. Jamais de fusion automatique.
#
# TROIS GARANTIES DURES :
#
# 1. AUCUNE SUPPRESSION. Le doublon n'est jamais effacé : il est NEUTRALISÉ.
#    `Client` ne porte pas (encore) de drapeau d'archivage — ajouter une
#    colonne supposerait une migration `crm`, hors du périmètre de cette
#    tâche. On utilise donc le mécanisme EXISTANT prévu pour ça :
#    `avertissement_bloquant` (une garde serveur refuse dès lors l'acceptation
#    et la facturation d'un devis pour ce client, patron XFAC28) + un
#    avertissement lisible, + un marqueur `custom_data['fusionne_dans']` qui
#    trace la cible et la date. La fiche reste consultable, son historique
#    intact, et la fusion est intégralement réversible à la main.
#
# 2. AUCUN ORPHELIN. Tout ce qui pointait le doublon pointe le survivant —
#    non pas une liste de quatre modèles écrite à la main (le dépôt compte
#    plus de trente FK vers `Client`), mais le parcours des relations inverses
#    déclarées par Django (`core.merge.repointer_relations`, la MÊME mécanique
#    que la fusion fournisseur/produit de `stock` — jamais une seconde
#    implémentation). Chaque relation est repointée dans son PROPRE point de
#    sauvegarde : une contrainte d'unicité qui refuse (le survivant a déjà sa
#    limite de crédit, par exemple) annule CETTE relation seule et le rapport
#    la NOMME, au lieu de faire échouer toute la fusion en silence.
#
# 3. AUCUN IMPORT D'APP ÉTRANGÈRE. Le parcours passe par l'API `_meta` de
#    Django, donc `crm` n'importe ni `ventes`, ni `facturation`, ni
#    `installations`, ni `sav`.


# ── CAD-G ── CAD74 — réveil saisonnier (`reveil_b`) ────────────────────────
# Le câblage vit dans `apps/crm/cadence_reveil_saison.py` (module autonome —
# ce fichier est partagé par des dizaines de tâches). Ces deux passe-plats
# sont le point d'entrée attendu par les appelants de `services` ; ils ne
# dupliquent aucune logique. Crochet planifié : AUCUN aujourd'hui — la pose
# se déclenche par un appel explicite, jamais à l'insu de la commerciale.


# ── CAD-I ── CAD90 — le registre couvre TOUTES les créations de lead ────────
#
# Audit L3 du 21/09/2026. ``enregistrer_consentement_lead`` n'était appelée
# que depuis le webhook du formulaire du site : un lead créé à la main par la
# commerciale (appel entrant, WhatsApp reçu au salon), un lead Meta Lead Ads
# ou un lead venu d'un document n'écrivaient RIEN au registre
# ``core.ConsentRecord`` — alors que la cadence démarre quand même et que sa
# touche n°1 est un WhatsApp, le canal le plus encadré.
#
# CE QUE ``granted`` VEUT DIRE ICI, ET CE QU'IL NE VEUT PAS DIRE. Il dit
# seulement si un CONSENTEMENT A ÉTÉ RECUEILLI — jamais si le traitement est
# licite. Sur ces chemins, aucune case n'a été cochée par la personne : la
# licéité vient de la BASE LÉGALE, tracée dans ``source``. Écrire
# ``granted=True`` pour faire joli fabriquerait une preuve fausse, ce qui est
# pire qu'une preuve absente (même raison que ``ip_confirmation`` laissée
# vide par l'intake web).
#
# LES DEUX BASES, SUR TEXTE PRIMAIRE (extraction du round 2 de l'audit, PDF
# adala.justice.gov.ma) :
#   * données NON collectées auprès de la personne (Meta, import, document) —
#     loi 09-08 art. 5 §3, avec l'information due « par tous moyens » de
#     l'art. 34 du décret 2-09-165 ;
#   * la personne a elle-même SOLLICITÉ le contact (appel entrant, message
#     WhatsApp, demande au salon) — relation précontractuelle à sa demande,
#     loi 09-08 art. 5. Le CNDP distingue les deux, le registre aussi.


# ── CAD-K ── CAD129 — « rappelez-moi » entre dans la FILE, pas dans la cloche ─
#
# Audit L3 du 21/09/2026. Un clic « rappelez-moi » écrivait une note, notifiait
# le responsable et son supérieur, et posait la préférence « joignable par
# téléphone » — mais ne créait AUCUNE touche. Si la notification est noyée dans
# la cloche, la demande la plus forte qu'un prospect puisse faire disparaît.
#
# LA RÈGLE : décaler, jamais redémarrer. Quand le lead a déjà un plan en cours,
# on RAMÈNE sa prochaine touche au prochain créneau d'appel et tout le reste du
# plan glisse du MÊME delta (``reporter_prochaine_touche`` le fait déjà, ancre
# comprise) : le lead garde sa position dans le protocole, on ne fabrique pas un
# second plan concurrent. Quand il n'a plus aucune touche ouverte (cadence
# terminée ou arrêtée), on pose UNE touche — une seule, jamais un plan.


# ── CAD164 — le LOCATAIRE : demander le propriétaire, sinon « Perdu — Locataire »
#
# Décision fondateur du 21/09/2026 : on demande le propriétaire ; s'il est
# joignable, on crée SA fiche, LIÉE à celle du locataire (le locataire reste le
# prescripteur : son prénom passe par la variable `{prescripteur}` du texte
# d'origine « recommandation », CAD127 — jamais en dur) ; sinon on clôt avec
# le motif EXISTANT « Locataire ». Aucune valeur d'énumération neuve : le motif
# existe (`MotifPerte`), le canal « Référence » aussi, et le lien entre les deux
# fiches est une NOTE d'historique de chaque côté — jamais une fusion
# automatique (conduite `FLUX_LOCATAIRE` du script d'appel).
