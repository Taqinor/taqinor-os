"""Derniers points d'entrée d'arrivée de lead (OCR, carte de visite, WhatsApp, livechat, ticket, import) (SPL24, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import logging

from . import activity, stages
from .cadence_plan import demarrer_cadence_contact
from .cadence_touche import reprendre_cadence_apres_reouverture
from .clients_identite import _email_identite
from .fiche_funnel import _STAGE_CONTACTED, _rang_funnel, appliquer_stage_lead
from .leads_attribution import default_responsable_for
from .leads_consentement import (
    BASE_LEGALE_NON_COLLECTEE,
    CONSENT_SOURCE_DOCUMENT,
    enregistrer_base_legale_lead,
)
from .leads_doublons import find_duplicates_by_contact, normalize_phone
from .leads_notifications import notify_new_lead
from .leads_score import recompute_lead_score
from .models import Lead, LeadActivity

logger = logging.getLogger(__name__)


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
