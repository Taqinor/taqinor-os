"""ADSDEEP27/28/29 — Boucle de retour CAPI « signatures » vers le CRM Dataset Meta.

Troisième famille d'événements CAPI du moteur, SÉPARÉE des deux existantes
(``capi_crm``/ADSENG32 = transitions d'étape ``crm.Lead`` ; ``ventes``/QJ9 =
``SignedQuote`` sur l'acceptation d'un devis). Ici on câble l'intégration Meta
*Conversion Leads* sur le CRM Dataset (dossier ``adsdeep-leads-capi.md`` §4) :

  * **ADSDEEP27** — sur chaque NOUVEAU deal signé Odoo (``odoo_signed_deals``),
    un événement ``signed_contract`` (l'ISSUE de la boucle) ;
  * **ADSDEEP28** — pour chaque lead Meta miroité (``MetaLeadMirror``), un
    événement AMONT ``lead_received`` (Meta exige AU MOINS deux étapes par
    ``lead_id`` : réception + issue) ;
  * **ADSDEEP29** — la table étape-STAGES.py → ``event_name`` Meta, en DATA
    (jamais une liste d'étapes codée en dur — règle #2).

Conformité au spec Conversion Leads :
  * ``action_source='system_generated'`` (OBLIGATOIRE), ``custom_data``
    ``event_source='crm'`` + ``lead_event_source='ERP'`` ;
  * match ``user_data`` : ``lead_id`` (leadgen Meta, JAMAIS haché) en priorité,
    sinon ``ph`` = SHA-256 du téléphone E.164 (chiffres seuls) ;
  * ``value`` + ``currency='MAD'`` du deal (optimisation par la valeur) ;
  * ``event_time`` ≤ 7 j avant l'envoi (sinon rabattu sur maintenant) ;
  * **NO-OP propre** sans ``CAPI_CRM_DATASET_ID`` + token : aucun appel réseau,
    aucune lecture Odoo (key-gated comme tout le moteur) ;
  * **IDEMPOTENCE** persistée : chaque événement (``event_key`` déterministe)
    n'est POSTé qu'UNE fois par société (marqueur ``CapiOdooEvent``) — le beat
    quotidien rejoue sans jamais dupliquer.

Le CRM est lu via ``apps.crm.selectors`` uniquement ; Odoo via les modules
``odoo_*`` d'``adsengine``. Les helpers de HACHAGE/transport/réglages sont
RÉUTILISÉS de ``capi_crm`` (jamais dupliqués).
"""
from __future__ import annotations

import datetime as _dt
import json as _json
import logging
import time
import urllib.parse
from decimal import Decimal, InvalidOperation

from .api_version import GRAPH_BASE_URL
# Réutilise les helpers d'ADSENG32 (hachage SHA-256, lecture de réglage,
# transport HTTP réel) — jamais dupliqués (instruction ADSDEEP).
from .capi_crm import _default_transport, _setting, _sha256
from .odoo_selectors import signed_deals as odoo_signed_deals

logger = logging.getLogger(__name__)

# ── Gating (env) — le CRM Dataset est SÉPARÉ du pixel site web (dossier §4) ────
_DATASET_KEY = 'CAPI_CRM_DATASET_ID'
# Token : un token dédié au dataset s'il existe, sinon le token CAPI partagé
# (même token System-User côté Meta). Key-gated comme le reste du moteur.
_TOKEN_KEYS = ('CAPI_CRM_ACCESS_TOKEN', 'META_CAPI_ACCESS_TOKEN')

# custom_data constants (dossier §4 — event_source/lead_event_source figés).
_EVENT_SOURCE = 'crm'
_LEAD_EVENT_SOURCE = 'ERP'
_CURRENCY = 'MAD'

# event_name des deux bornes de la boucle (littéraux Meta — PAS des clés STAGES).
SIGNED_EVENT_NAME = 'signed_contract'
LEAD_RECEIVED_EVENT_NAME = 'lead_received'

# Reconstruction E.164 : ``normalize_phone`` (QW10) retire l'indicatif marocain
# (212) et les zéros initiaux → on le repose avant de hacher, pour que le ``ph``
# corresponde au numéro pays-inclus que Meta détient (matching E.164, chiffres
# seuls). Réalité TAQINOR : numéros marocains.
_DEFAULT_COUNTRY_CODE = '212'

# Meta rejette un ``event_time`` de plus de 7 j (ou dans le futur).
_EVENT_TIME_MAX_AGE = 7 * 24 * 3600


def _dataset_id():
    return _setting(_DATASET_KEY)


def _token():
    for key in _TOKEN_KEYS:
        val = _setting(key)
        if val:
            return val
    return ''


def is_configured():
    """CRM Dataset activable ? (dataset id + token présents). Sans quoi tout
    l'émetteur no-ope (aucun appel réseau, aucune lecture Odoo)."""
    return bool(_dataset_id()) and bool(_token())


# ── Helpers PURS (aucune I/O) ─────────────────────────────────────────────────

def _e164_digits(phone_norm):
    """Clé téléphone QW10 (indicatif 212 retiré) → chiffres E.164 complets
    (indicatif marocain reposé), ou '' si vide."""
    digits = ''.join(c for c in (phone_norm or '') if c.isdigit())
    if not digits:
        return ''
    return f'{_DEFAULT_COUNTRY_CODE}{digits}'


def _deal_value(deal):
    """Montant du deal (``amount_mad``) en float pour ``custom_data.value``
    (0.0 si illisible — jamais d'exception)."""
    try:
        return float(Decimal(str(deal.get('amount_mad'))))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0


def _parse_deal_time(value):
    """date/datetime Odoo (str ``YYYY-MM-DD[ HH:MM:SS]`` / date / epoch) → unix
    UTC, ou None si illisible."""
    if value in (None, '', False):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace('T', ' ')
    # datetime complet (YYYY-MM-DD HH:MM:SS) puis date seule (YYYY-MM-DD).
    for text_slice, fmt in ((text[:19], '%Y-%m-%d %H:%M:%S'),
                            (text[:10], '%Y-%m-%d')):
        try:
            parsed = _dt.datetime.strptime(text_slice, fmt)
        except ValueError:
            continue
        return int(parsed.replace(tzinfo=_dt.timezone.utc).timestamp())
    return None


def _event_time_for(deal, now):
    """``event_time`` du deal, rabattu sur ``now`` si absent, futur, ou > 7 j
    (contrainte Meta)."""
    parsed = _parse_deal_time(deal.get('date'))
    if parsed is None or parsed > now or (now - parsed) > _EVENT_TIME_MAX_AGE:
        return now
    return parsed


def build_signed_event(company, deal, *, now=None):
    """ADSDEEP27 — Construit l'événement CAPI ``signed_contract`` d'un deal signé
    Odoo (PUR côté payload ; une seule lecture DB pour résoudre le ``lead_id``).

    ``user_data`` : ``lead_id`` = leadgen_id d'un ``MetaLeadMirror`` correspondant
    au téléphone (JAMAIS haché) en priorité, sinon ``ph`` = SHA-256 du téléphone
    E.164. Renvoie ``{'eligible', 'reason', 'event'|None, 'event_key'|None}`` —
    inéligible s'il n'y a AUCUNE clé de match (jamais de PII en clair)."""
    now = int(now if now is not None else time.time())
    phone_norm = deal.get('phone_norm') or ''
    lead_id = _lead_id_for_phone(company, phone_norm)

    user_data = {}
    if lead_id:
        user_data['lead_id'] = lead_id
    else:
        e164 = _e164_digits(phone_norm)
        if e164:
            user_data['ph'] = [_sha256(e164)]

    if not user_data:
        return {'eligible': False, 'reason': 'no_match_key',
                'event': None, 'event_key': None}

    # Clé de dedup STABLE par deal : id de lead Odoo si connu, sinon téléphone
    # normalisé (déterministe entre deux passages du beat).
    deal_ref = deal.get('lead_id') or phone_norm or 'unknown'
    event_key = f'odoo_signed:{deal_ref}'
    event = {
        'event_name': SIGNED_EVENT_NAME,
        'event_time': _event_time_for(deal, now),
        'event_id': event_key,
        'action_source': 'system_generated',
        'user_data': user_data,
        'custom_data': {
            'event_source': _EVENT_SOURCE,
            'lead_event_source': _LEAD_EVENT_SOURCE,
            'value': _deal_value(deal),
            'currency': _CURRENCY,
        },
    }
    return {'eligible': True, 'reason': 'ok',
            'event': event, 'event_key': event_key}


# ── Résolution lead_id + marqueur d'idempotence (I/O) ─────────────────────────

def _lead_id_for_phone(company, phone_norm):
    """leadgen_id d'un ``MetaLeadMirror`` de la société dont le ``phone_key``
    (normalisation QW10, la MÊME que ``deal['phone_norm']``) correspond, ou ''."""
    if not phone_norm:
        return ''
    from .models import MetaLeadMirror
    leadgen = (MetaLeadMirror.objects
               .filter(company=company, phone_key=phone_norm)
               .exclude(leadgen_id='')
               .values_list('leadgen_id', flat=True)
               .first())
    return leadgen or ''


def _already_sent(company, event_key):
    from .models import CapiOdooEvent
    return CapiOdooEvent.objects.filter(
        company=company, event_key=event_key).exists()


def _mark_sent(company, event_key, event_name):
    """Pose le marqueur d'idempotence APRÈS un envoi réussi. Une course entre
    deux passages (unicité (company, event_key)) ne lève jamais."""
    from django.db import IntegrityError

    from .models import CapiOdooEvent
    try:
        CapiOdooEvent.objects.create(
            company=company, event_key=event_key, event_name=event_name)
    except IntegrityError:
        pass


def _send_event(event, *, transport=None):
    """POST un événement au CRM Dataset. True si envoyé, False sinon (best-effort,
    ne lève JAMAIS). ``transport`` (``(url, payload)->(status, body)``) injectable
    en test ; par défaut l'envoi urllib réel réutilisé de ``capi_crm``."""
    url = (f'{GRAPH_BASE_URL}/{_dataset_id()}/events?'
           + urllib.parse.urlencode({'access_token': _token()}))
    payload = _json.dumps({'data': [event]}).encode('utf-8')
    send = transport or _default_transport
    try:
        status, _body = send(url, payload)
        logger.info('ADSDEEP27/28: CAPI event %s envoyé — status %s',
                    event['event_id'], status)
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('ADSDEEP27/28: CAPI event %s échoué : %s',
                       event['event_id'], exc)
        return False


def emit_signed_deals(company, *, since=None, client=None, now=None,
                      transport=None):
    """ADSDEEP27 — Émet un événement ``signed_contract`` par NOUVEAU deal signé
    Odoo, idempotent (marqueur ``CapiOdooEvent``). NO-OP propre sans dataset/token
    (aucune lecture Odoo ni appel réseau). Best-effort — ne lève jamais.

    Renvoie ``{'emitted', 'skipped', 'reason'}``."""
    result = {'emitted': 0, 'skipped': 0, 'reason': 'ok'}
    if not is_configured():
        result['reason'] = 'not_configured'
        return result
    try:
        deals = odoo_signed_deals(since=since, client=client)
    except Exception as exc:  # noqa: BLE001 — dégradation propre (jamais un 500)
        logger.warning('ADSDEEP27: lecture Odoo échouée : %s', exc)
        result['reason'] = 'odoo_error'
        return result

    for deal in deals:
        built = build_signed_event(company, deal, now=now)
        if not built['eligible']:
            result['skipped'] += 1
            continue
        event_key = built['event_key']
        if _already_sent(company, event_key):
            result['skipped'] += 1  # déjà émis — jamais deux fois par deal
            continue
        if _send_event(built['event'], transport=transport):
            _mark_sent(company, event_key, built['event']['event_name'])
            result['emitted'] += 1
        else:
            result['skipped'] += 1  # échec HTTP : pas de marqueur → réessai demain
    return result
