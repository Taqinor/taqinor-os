"""ADSENG32 — Émetteur CAPI CRM-stage (SÉPARÉ de l'émetteur signature QJ9).

Deux familles d'événements CAPI, proprement séparées (dd-attribution part c,
respecte l'instruction « ne jamais fusionner » de CLAUDE.md règle #2) :

  * **QJ9** (``apps/ventes/services.py``, INTACT ici) — événement ``SignedQuote``
    sur l'acceptation d'un DEVIS (couche document, règle #4), pour l'optimisation
    ROAS standard. Ce module N'Y TOUCHE PAS.
  * **ADSENG32** (ce module) — événement lead-QUALIFIÉ sur une TRANSITION de
    ``crm.Lead.stage`` (couche pipeline, règle #2), pour l'intégration Meta
    *Conversion Leads*. Deux produits Meta différents, deux couches ERP
    différentes — on câble chacune à l'intégration faite pour cette séparation.

Choix conformes au spec Conversion Leads (primary-sourced, dd-attribution §4.4) :
  * ``event_name`` = la CLÉ STAGES.py de la nouvelle étape (``CONTACTED`` /
    ``QUOTE_SENT`` / ``SIGNED`` …), JAMAIS codée en dur — Meta dit explicitement
    de refléter « les étapes de votre CRM » ; on émet sur chaque transition
    AVANT et on laisse l'UI Meta décider laquelle est « qualifiée » ;
  * ``action_source='system_generated'`` + ``custom_data.event_source='crm'`` +
    ``custom_data.lead_event_source='ERP CRM'`` (neutre, white-label — jamais la
    marque plateforme en dur, SCA29) ;
  * match via ``lead_id`` = leadgen_id (= ``Lead.external_id`` quand
    ``external_system='meta_lead_ads'``) + téléphone/email HACHÉS SHA-256 ;
  * ``event_id`` DÉTERMINISTE (dedup Meta 48 h) — un re-save ne double jamais ;
  * gaté par son PROPRE flag ``META_CRM_STAGE_CAPI_ENABLED`` (l'intégration
    Conversion Leads a son propre opt-in dans Events Manager — action fondateur),
    puis ``META_CAPI_ACCESS_TOKEN`` / ``META_CAPI_PIXEL_ID`` ;
  * version d'API depuis la SOURCE UNIQUE partagée ``api_version.GRAPH_BASE_URL``
    (v25 courante ; jamais la v19 expirée codée en dur).

Le CRM est lu UNIQUEMENT via ``apps.crm.selectors`` (jamais un import de
``apps.crm.models`` — contrat import-linter). Le déclencheur de transition est un
récepteur ``pre_save``/``post_save`` sur ``crm.Lead`` (câblé dans ``apps.py``
``ready()`` via ``apps.get_model`` — pas d'import statique du modèle). Ne lève
JAMAIS depuis le récepteur : un échec CAPI ne casse jamais un save de lead.

**PUB30** ajoute un TROISIÈME événement, dédié (namespace ``apptdone:``,
event_name ``visite_technique_effectuee``), sur la transition d'un
``crm.Appointment`` vers EFFECTUE — même famille/gating que ci-dessus, câblé
via ``core.events.appointment_effectue`` (émis par ``crm``, jamais importé
ici) + ``apps/adsengine/receivers.py``. **PUB31** ajoute un enrichissement
OPTIONNEL (flag ``META_CRM_STAGE_CAPI_VALUE_ENABLED``, OFF par défaut) :
``custom_data.value/currency`` = montant TTC du devis lié, UNIQUEMENT sur
QUOTE_SENT (lu via ``apps.ventes.selectors.devis_value_for_lead`` — fonction
fine, jamais un import de ``apps.ventes.models``) — ``signed_contract``
(capi_odoo) n'est jamais touché par ce module.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time

logger = logging.getLogger(__name__)

# Flag d'opt-in PROPRE (distinct du token QJ9) : Conversion Leads est une
# intégration séparée avec sa propre étape de connexion côté Meta.
_ENABLED_KEY = 'META_CRM_STAGE_CAPI_ENABLED'
_TOKEN_KEY = 'META_CAPI_ACCESS_TOKEN'
_PIXEL_KEY = 'META_CAPI_PIXEL_ID'
# PUB31 — flag SÉPARÉ (OFF par défaut) : enrichit UNIQUEMENT l'événement
# QUOTE_SENT avec custom_data.value/currency (montant TTC du devis lié). OFF =
# byte-identique. Ne touche JAMAIS signed_contract (capi_odoo, intact).
_VALUE_ENABLED_KEY = 'META_CRM_STAGE_CAPI_VALUE_ENABLED'

# custom_data.lead_event_source (primary-sourced : nom de la source CRM).
_LEAD_EVENT_SOURCE = 'ERP CRM'

_STASH_ATTR = '_adseng32_old_stage'

# PUB30 — Table statut Appointment -> event_name Meta (DONNÉES, jamais une
# chaîne en dur dispersée dans le code). ``crm.Appointment.Statut`` n'est PAS
# une clé STAGES.py (règle #2 ne s'applique qu'au funnel pipeline) — c'est un
# vocabulaire adsengine-only, donc défini ici, pas lu depuis un sélecteur crm.
APPOINTMENT_EVENT_NAMES = {
    'effectue': 'visite_technique_effectuee',
}


def appointment_event_name(statut):
    """Nom d'événement CAPI pour un statut ``Appointment``, ou '' si non
    mappé (jamais une exception — un statut futur non mappé est simplement
    inéligible)."""
    return APPOINTMENT_EVENT_NAMES.get(statut, '')


def _sha256(value):
    return hashlib.sha256((value or '').strip().lower().encode()).hexdigest()


def _setting(name):
    """Valeur d'un réglage (settings puis environnement), strip. '' si absent."""
    from django.conf import settings
    return (getattr(settings, name, None)
            or os.environ.get(name, '') or '').strip()


def _enabled():
    """L'intégration CRM-stage est-elle explicitement activée ?"""
    return _setting(_ENABLED_KEY).lower() in ('1', 'true', 'yes', 'on')


def _value_enabled():
    """PUB31 — l'enrichissement value/currency sur QUOTE_SENT est-il activé ?
    OFF par défaut (comportement byte-identique)."""
    return _setting(_VALUE_ENABLED_KEY).lower() in ('1', 'true', 'yes', 'on')


def is_forward_transition(old_stage, new_stage):
    """Transition AVANT dans l'entonnoir (hors COLD), d'après l'ordre STAGES.py
    (jamais codé en dur — lu via le sélecteur CRM). Une entrée directe sur une
    étape d'entonnoir (``old_stage`` None, ou venant de COLD/inconnu) compte
    comme une transition avant. Entrer en COLD n'est jamais « avant »."""
    from apps.crm.selectors import pipeline_stage_order
    order = pipeline_stage_order()
    funnel = order['funnel']
    if new_stage == order['cold'] or new_stage not in funnel:
        return False
    new_rank = funnel.index(new_stage)
    if old_stage is None or old_stage not in funnel:
        return True
    return new_rank > funnel.index(old_stage)


def build_stage_event(company, lead_id, new_stage, *, old_stage=None, now=None):
    """Construit l'événement CAPI CRM-stage (PUR — aucune I/O, aucun flag).

    Renvoie ``{'eligible', 'reason', 'event'|None, 'match_quality'}``. ``event``
    n'est présent que si le lead est éligible (transition avant + origine Meta +
    au moins une clé de match). ``match_quality`` rend VISIBLE la qualité de match
    (quelles clés — lead_id/ph/em/fbc — sont présentes), le moniteur EMQ local."""
    now = int(now if now is not None else time.time())
    if not is_forward_transition(old_stage, new_stage):
        return {'eligible': False, 'reason': 'not_forward',
                'event': None, 'match_quality': {}}

    from apps.crm.selectors import lead_capi_identifiers
    ids = lead_capi_identifiers(company, lead_id)
    if ids is None:
        return {'eligible': False, 'reason': 'lead_not_found',
                'event': None, 'match_quality': {}}
    if not ids['is_meta_origin']:
        return {'eligible': False, 'reason': 'not_meta_origin',
                'event': None, 'match_quality': {}}

    user_data = {}
    if ids['leadgen_id']:
        # Clé de match préférée de Meta (leadgen_id 15-17 chiffres) — NON hachée.
        user_data['lead_id'] = ids['leadgen_id']
    phone_digits = ''.join(c for c in ids['phone'] if c.isdigit())
    if phone_digits:
        user_data['ph'] = [_sha256(phone_digits)]
    if ids['email']:
        user_data['em'] = [_sha256(ids['email'])]
    if ids['fbclid']:
        user_data['fbc'] = f'fb.1.{now * 1000}.{ids["fbclid"]}'

    if not user_data:
        return {'eligible': False, 'reason': 'no_match_key',
                'event': None, 'match_quality': {}}

    match_quality = {
        'has_lead_id': 'lead_id' in user_data,
        'has_phone': 'ph' in user_data,
        'has_email': 'em' in user_data,
        'has_fbc': 'fbc' in user_data,
        'match_keys': len(user_data),
    }

    # event_id DÉTERMINISTE : leadgen_id (stable) sinon lead_id, + étape. Deux
    # émissions de même (event_name, event_id) sous 48 h sont dé-dupliquées.
    ref = ids['leadgen_id'] or str(lead_id)
    event_id = f'crmstage:{ref}:{new_stage}'
    event = {
        # event_name = clé STAGES.py de la nouvelle étape (jamais en dur).
        'event_name': new_stage,
        'event_time': now,
        'event_id': event_id,
        'action_source': 'system_generated',
        'user_data': user_data,
        'custom_data': {
            'event_source': 'crm',
            'lead_event_source': _LEAD_EVENT_SOURCE,
            'lead_stage': new_stage,
        },
    }
    # PUB31 — enrichissement OPTIONNEL (flag OFF par défaut = byte-identique) :
    # custom_data.value/currency = montant TTC du devis lié, UNIQUEMENT sur la
    # transition vers QUOTE_SENT (clé STAGES.py lue via le sélecteur CRM,
    # jamais en dur). ``signed_contract`` (capi_odoo) porte déjà value/
    # currency sur sa propre transition — ce module ne le touche jamais.
    from apps.crm.selectors import pipeline_stage_order as _psorder
    if new_stage == _psorder()['quote_sent'] and _value_enabled():
        from apps.ventes.selectors import devis_value_for_lead
        devis_value = devis_value_for_lead(lead_id, company)
        if devis_value is not None:
            event['custom_data']['value'] = devis_value['value']
            event['custom_data']['currency'] = devis_value['currency']
    return {'eligible': True, 'reason': 'ok', 'event': event,
            'match_quality': match_quality}


def _default_transport(url, payload):  # pragma: no cover - réseau réel
    """Envoi HTTP réel (POST JSON). Isolé pour être simulable en test."""
    import urllib.request
    req = urllib.request.Request(
        url, data=payload,
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
        return resp.status, resp.read().decode('utf-8', errors='replace')


def emit_lead_stage_event(company, lead_id, new_stage, *, old_stage=None,
                          now=None, transport=None):
    """ADSENG32 — Émet (ou prépare) l'événement CAPI CRM-stage. Best-effort :
    ne lève JAMAIS. Renvoie un dict de résultat ``{'emitted', 'reason',
    'event_id'?, 'event_name'?, 'match_quality'?}``.

    Chaîne de portes : transition avant → origine Meta → clé de match → flag
    ``META_CRM_STAGE_CAPI_ENABLED`` → token → pixel/dataset. Une porte non
    franchie ⇒ ``emitted=False`` + une ``reason`` explicite (jamais un échec
    silencieux). ``transport`` (callable ``(url, payload)->(status, body)``) est
    injectable pour les tests — par défaut l'envoi urllib réel."""
    try:
        built = build_stage_event(
            company, lead_id, new_stage, old_stage=old_stage, now=now)
    except Exception:  # noqa: BLE001 — jamais casser le save du lead
        logger.warning('ADSENG32: construction event CRM-stage échouée',
                       exc_info=True)
        return {'emitted': False, 'reason': 'build_error'}

    if not built['eligible']:
        return {'emitted': False, 'reason': built['reason']}

    event = built['event']
    result = {
        'emitted': False,
        'event_id': event['event_id'],
        'event_name': event['event_name'],
        'match_quality': built['match_quality'],
    }

    if not _enabled():
        result['reason'] = 'disabled'
        logger.info('ADSENG32: CRM-stage CAPI désactivé (flag) — event %s prêt '
                    '(log seul)', event['event_id'])
        return result

    token = _setting(_TOKEN_KEY)
    if not token:
        result['reason'] = 'no_token'
        logger.info('ADSENG32: CRM-stage CAPI event %s prêt — token absent '
                    '(log seul)', event['event_id'])
        return result

    pixel = _setting(_PIXEL_KEY)
    if not pixel:
        result['reason'] = 'no_pixel'
        logger.info('ADSENG32: CRM-stage CAPI event %s prêt — pixel/dataset '
                    'absent (log seul)', event['event_id'])
        return result

    import json as _json
    import urllib.parse

    from .api_version import GRAPH_BASE_URL
    url = (f'{GRAPH_BASE_URL}/{pixel}/events?'
           + urllib.parse.urlencode({'access_token': token}))
    payload = _json.dumps({'data': [event]}).encode('utf-8')
    send = transport or _default_transport
    try:
        status, body = send(url, payload)
        result['emitted'] = True
        result['reason'] = 'sent'
        logger.info('ADSENG32: CRM-stage CAPI event %s envoyé — status %s',
                    event['event_id'], status)
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        result['reason'] = 'http_error'
        logger.warning('ADSENG32: CRM-stage CAPI event %s échoué : %s',
                       event['event_id'], exc)
    return result


# ── PUB30 — Événement CAPI dédié « visite technique effectuée » ───────────────
# MÊME FAMILLE que le CRM-stage CAPI ci-dessus (mêmes identifiants de match via
# lead_capi_identifiers, même origine Meta requise, même gating
# META_CRM_STAGE_CAPI_ENABLED/token/pixel) mais un ``event_name`` DISTINCT
# (``visite_technique_effectuee``, jamais une clé STAGES.py) : le RDV terrain
# honoré (Appointment EFFECTUE) est le signal offline le plus proche de la
# vente, jusqu'ici invisible de Meta.

def build_appointment_event(company, lead_id, appointment_id, statut, *,
                            now=None):
    """Construit l'événement CAPI « visite technique effectuée » (PUR — aucune
    I/O, aucun flag). Renvoie ``{'eligible', 'reason', 'event'|None,
    'match_quality'}`` — même contrat que ``build_stage_event``."""
    now = int(now if now is not None else time.time())
    event_name = appointment_event_name(statut)
    if not event_name:
        return {'eligible': False, 'reason': 'unmapped_statut',
                'event': None, 'match_quality': {}}

    from apps.crm.selectors import lead_capi_identifiers
    ids = lead_capi_identifiers(company, lead_id)
    if ids is None:
        return {'eligible': False, 'reason': 'lead_not_found',
                'event': None, 'match_quality': {}}
    if not ids['is_meta_origin']:
        return {'eligible': False, 'reason': 'not_meta_origin',
                'event': None, 'match_quality': {}}

    user_data = {}
    if ids['leadgen_id']:
        user_data['lead_id'] = ids['leadgen_id']
    phone_digits = ''.join(c for c in ids['phone'] if c.isdigit())
    if phone_digits:
        user_data['ph'] = [_sha256(phone_digits)]
    if ids['email']:
        user_data['em'] = [_sha256(ids['email'])]
    if ids['fbclid']:
        user_data['fbc'] = f'fb.1.{now * 1000}.{ids["fbclid"]}'

    if not user_data:
        return {'eligible': False, 'reason': 'no_match_key',
                'event': None, 'match_quality': {}}

    match_quality = {
        'has_lead_id': 'lead_id' in user_data,
        'has_phone': 'ph' in user_data,
        'has_email': 'em' in user_data,
        'has_fbc': 'fbc' in user_data,
        'match_keys': len(user_data),
    }

    # event_id DÉTERMINISTE par rendez-vous : un re-save du MÊME Appointment
    # sur EFFECTUE (dedup côté récepteur crm) ET un rejeu Meta (48 h) sont
    # tous deux dé-dupliqués sur cette même clé.
    ref = ids['leadgen_id'] or str(lead_id)
    event_id = f'apptdone:{ref}:{appointment_id}'
    event = {
        'event_name': event_name,
        'event_time': now,
        'event_id': event_id,
        'action_source': 'system_generated',
        'user_data': user_data,
        'custom_data': {
            'event_source': 'crm',
            'lead_event_source': _LEAD_EVENT_SOURCE,
            'appointment_id': appointment_id,
        },
    }
    return {'eligible': True, 'reason': 'ok', 'event': event,
            'match_quality': match_quality}


def emit_appointment_effectue_event(company, lead_id, appointment_id, *,
                                    statut='effectue', now=None,
                                    transport=None):
    """Émet (ou prépare) l'événement CAPI « visite technique effectuée ».
    Best-effort : ne lève JAMAIS. MÊME chaîne de portes et MÊME gating
    (``META_CRM_STAGE_CAPI_ENABLED``/token/pixel) que
    ``emit_lead_stage_event`` — sans clés configurées : no-op silencieux
    loggué (jamais une exception)."""
    try:
        built = build_appointment_event(
            company, lead_id, appointment_id, statut, now=now)
    except Exception:  # noqa: BLE001 — jamais casser l'appelant
        logger.warning('PUB30: construction event visite-effectuée échouée',
                       exc_info=True)
        return {'emitted': False, 'reason': 'build_error'}

    if not built['eligible']:
        return {'emitted': False, 'reason': built['reason']}

    event = built['event']
    result = {
        'emitted': False,
        'event_id': event['event_id'],
        'event_name': event['event_name'],
        'match_quality': built['match_quality'],
    }

    if not _enabled():
        result['reason'] = 'disabled'
        logger.info('PUB30: visite-effectuée CAPI désactivé (flag) — event '
                    '%s prêt (log seul)', event['event_id'])
        return result

    token = _setting(_TOKEN_KEY)
    if not token:
        result['reason'] = 'no_token'
        logger.info('PUB30: visite-effectuée CAPI event %s prêt — token '
                    'absent (log seul)', event['event_id'])
        return result

    pixel = _setting(_PIXEL_KEY)
    if not pixel:
        result['reason'] = 'no_pixel'
        logger.info('PUB30: visite-effectuée CAPI event %s prêt — pixel/'
                    'dataset absent (log seul)', event['event_id'])
        return result

    import json as _json
    import urllib.parse

    from .api_version import GRAPH_BASE_URL
    url = (f'{GRAPH_BASE_URL}/{pixel}/events?'
           + urllib.parse.urlencode({'access_token': token}))
    payload = _json.dumps({'data': [event]}).encode('utf-8')
    send = transport or _default_transport
    try:
        status, body = send(url, payload)
        result['emitted'] = True
        result['reason'] = 'sent'
        logger.info('PUB30: visite-effectuée CAPI event %s envoyé — status %s',
                    event['event_id'], status)
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        result['reason'] = 'http_error'
        logger.warning('PUB30: visite-effectuée CAPI event %s échoué : %s',
                       event['event_id'], exc)
    return result


def emq_monitor(company):
    """ADSENG32 — Moniteur EMQ (Event Match Quality) LOCAL, sans appel réseau.

    Le score EMQ réel (0-10) exige l'API Dataset Quality de Meta (séparée, non
    inline dans la réponse ``/events``) ; on rend « visible » ce qu'on peut sans
    elle : la DISPONIBILITÉ de l'intégration (flag + token présents) et la
    COUVERTURE DE MATCH attendue (proportion de leads Meta portant un identifiant
    fort — leadgen_id ou téléphone), lue via ``crm.selectors``. Renvoie ::

        {'enabled': bool, 'token_present': bool, 'dataset_quality_api':
         {'available': bool}, 'match_coverage': {...}}
    """
    from apps.crm.selectors import meta_lead_match_coverage
    token_present = bool(_setting(_TOKEN_KEY))
    return {
        'enabled': _enabled(),
        'token_present': token_present,
        # L'API Dataset Quality n'est joignable que si un token existe.
        'dataset_quality_api': {'available': token_present},
        'match_coverage': meta_lead_match_coverage(company),
    }


# ── Câblage du déclencheur de transition (récepteur sur crm.Lead) ─────────────

def _capture_old_stage(sender, instance, **kwargs):
    """``pre_save`` : capture l'ANCIENNE étape (la base porte encore l'ancienne
    valeur) via le sélecteur CRM, pour n'émettre que sur une VRAIE transition.
    Un lead neuf (pas de pk) → ancienne étape None.

    PERF : porte OFF par défaut (``META_CRM_STAGE_CAPI_ENABLED``) → on ne touche
    JAMAIS la base sur le save d'un lead tant que l'intégration n'est pas activée
    (ce récepteur est câblé app-wide sur chaque save de ``crm.Lead``)."""
    if not _enabled():
        return
    old = None
    if getattr(instance, 'pk', None):
        try:
            from apps.crm.selectors import lead_current_stage
            # company_id (int) évite de charger l'objet Company à chaque save.
            old = lead_current_stage(
                getattr(instance, 'company_id', None), instance.pk)
        except Exception:  # noqa: BLE001 — jamais casser le save
            old = None
    setattr(instance, _STASH_ATTR, old)


def _emit_on_stage_change(sender, instance, created, **kwargs):
    """``post_save`` : sur une transition d'étape AVANT, émet l'événement CAPI
    CRM-stage. Best-effort — jamais d'exception remontée au save du lead."""
    if not _enabled():
        return
    try:
        new_stage = getattr(instance, 'stage', None)
        if not new_stage:
            return
        old_stage = getattr(instance, _STASH_ATTR, None)
        if not created and old_stage == new_stage:
            return  # save sans changement d'étape → rien à émettre.
        emit_lead_stage_event(
            getattr(instance, 'company_id', None), instance.pk, new_stage,
            old_stage=old_stage)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('ADSENG32: récepteur CRM-stage CAPI échoué',
                       exc_info=True)


def connect(sender=None):
    """Câble les récepteurs ``pre_save``/``post_save`` sur ``crm.Lead``.

    ``sender`` résolu via ``apps.get_model('crm', 'Lead')`` (registre d'apps —
    PAS un import statique de ``apps.crm.models``, donc conforme import-linter
    et à la règle « jamais importer les modèles crm »). Idempotent (``dispatch_uid``).
    Appelé depuis ``AdsengineConfig.ready()``."""
    from django.apps import apps as django_apps
    from django.db.models.signals import post_save, pre_save

    if sender is None:
        sender = django_apps.get_model('crm', 'Lead')
    pre_save.connect(
        _capture_old_stage, sender=sender,
        dispatch_uid='adseng32_capture_old_stage')
    post_save.connect(
        _emit_on_stage_change, sender=sender,
        dispatch_uid='adseng32_emit_on_stage_change')
