"""ADSDEEP57/58/59 — Audiences Meta (Custom depuis CRM / Lookalike / Engagement).

Trois familles, DÉLIBÉRÉMENT séparées par leur exposition aux données :

  * **ADSDEEP57 — Custom Audiences depuis le CRM** (ce fichier). Identifiants
    de contact (email/téléphone) NORMALISÉS puis HACHÉS SHA-256 côté serveur,
    envoyés par sessions ≤10 000 (``usersreplace`` = remplacement ATOMIQUE).
  * **ADSDEEP58 — Lookalikes**. Dérivés d'une audience seed déjà peuplée.
  * **ADSDEEP59 — Audiences d'engagement**. Objets purement Meta-side
    (interactions formulaire/Page/IG) — AUCUNE donnée CRM n'est envoyée.

GATE CONSENTEMENT (ADSDEEP57 & 58 — XMKT36, consentement 1st-party / loi 09-08) :
tout code qui émet des identifiants CRM (Custom Audience et son Lookalike dérivé)
est derrière le flag ``META_CUSTOM_AUDIENCE_CONSENT``, **OFF PAR DÉFAUT**. Flag
OFF ⇒ **AUCUN appel réseau** (create / users / usersreplace / lookalike / delete /
poll) : la fonction calcule et renvoie quand même le résumé (compteurs hachés
localement) pour la prévisualisation UI, mais RIEN ne quitte le serveur. Poser un
vrai flag est une DÉCISION fondateur, et n'est valable qu'après l'acceptation
HUMAINE des « Custom Audience Terms » sur
https://business.facebook.com/ads/manage/customaudiences/tos/ (étape fondateur,
jamais automatisée — un 1er appel non accepté renvoie « Custom Audience Terms not
yet accepted »).

INVARIANT PII (permanent) : email/téléphone sont normalisés puis hachés SHA-256
(via ``capi_crm._sha256``, le MÊME primitif que l'émetteur CAPI) AVANT toute
construction de payload. Aucune valeur en clair n'est jamais placée dans un
payload — garanti par test (la valeur brute n'apparaît nulle part).

ADSDEEP59 (engagement) N'EST PAS gated : aucune donnée CRM ne transite (les
event_sources sont des objets Meta-side), donc rien à consentir côté 1st-party.

Le CRM est lu UNIQUEMENT via ``apps.crm.selectors`` (jamais un import de
``apps.crm.models`` — contrat import-linter) ; les identifiants de contact
arrivent déjà sous forme de dicts ``{'email', 'telephone'}`` (sélecteurs XMKT36
``lead_contact_identifiers`` / ``clients_contact_identifiers``).
"""
from __future__ import annotations

import os
import re

# Flag de consentement Custom Audience (ADSDEEP57/58). OFF par défaut : sans lui,
# AUCUNE donnée CRM ne quitte le serveur (aucun appel réseau).
CONSENT_ENV_KEY = 'META_CUSTOM_AUDIENCE_CONSENT'

# Acceptation HUMAINE des CGU Custom Audience (étape fondateur, jamais
# automatisée) — surfacée dans chaque résumé pour l'UI.
CUSTOM_AUDIENCE_TOS_URL = (
    'https://business.facebook.com/ads/manage/customaudiences/tos/')

# Fenêtre de session Meta : 10 000 lignes MAX par appel.
MAX_USERS_PER_SESSION = 10000

# Schéma d'identifiants hachés (dossier §1 : clés EMAIL / PHONE).
SCHEMA = ['EMAIL', 'PHONE']

# ADSDEEP58 — colonne value-based (valeur client = montant du devis), NON hachée.
VALUE_SCHEMA_KEY = 'LOOKALIKE_VALUE'

# ADSDEEP58 — seed minimum matché pour utiliser/seeder un lookalike (dossier §1/§2).
LOOKALIKE_MIN_SEED = 100

# ADSDEEP58 — ratio MA d'un lookalike : 1 % à 5 % (dossier §2).
MA_LOOKALIKE_MIN_RATIO = 0.01
MA_LOOKALIKE_MAX_RATIO = 0.05


def _setting(name):
    """Valeur d'un réglage (settings puis environnement), strip. '' si absent.
    Même résolution que ``capi_crm._setting`` (testable via override_settings)."""
    from django.conf import settings
    return (getattr(settings, name, None)
            or os.environ.get(name, '') or '').strip()


def custom_audience_consent_enabled():
    """Le consentement d'export Custom Audience est-il ACTIVÉ ? OFF par défaut.

    C'est l'UNIQUE porte : tant qu'elle est fermée, aucune fonction de ce module
    n'émet la moindre requête réseau pour une audience CRM (57/58)."""
    return _setting(CONSENT_ENV_KEY).lower() in ('1', 'true', 'yes', 'on')


# ── Normalisation + hachage (norme Meta customaudiences) ─────────────────────

def _normalize_email(email):
    """Norme Meta : trim + minuscules. '' si absent."""
    return (email or '').strip().lower()


def _normalize_phone(phone):
    """Norme Meta : chiffres uniquement, AVEC indicatif pays (212…).

    Réutilise la normalisation marocaine existante (``ventes.utils.phone``, déjà
    importée ailleurs dans adsengine) quand elle matche ; sinon repli chiffres
    bruts (0X… → 212X…). '' si absent."""
    brut = (phone or '').strip()
    if not brut:
        return ''
    try:
        from apps.ventes.utils.phone import normalize_ma_phone
        norme = normalize_ma_phone(brut)
        if norme:
            return norme
    except Exception:  # pragma: no cover - défensif
        pass
    chiffres = re.sub(r'\D', '', brut)
    if chiffres.startswith('0') and len(chiffres) == 10:
        chiffres = '212' + chiffres[1:]
    return chiffres


def build_upload(contacts):
    """Construit ``(schema, rows)`` HACHÉS depuis des dicts contact CRM.

    ``contacts`` : liste ``{'email', 'telephone', 'value'?}`` (sélecteurs crm).
    email/téléphone sont normalisés puis hachés SHA-256 (``capi_crm._sha256``,
    même primitif que l'émetteur CAPI) ; un champ vide donne '' (jamais un hash
    de chaîne vide). Une ligne sans AUCUN identifiant est ignorée.

    Si au moins un contact porte une ``value`` (ADSDEEP58 value-based, montant du
    devis), la colonne ``LOOKALIKE_VALUE`` est ajoutée au schéma — NON hachée
    (ce n'est pas une PII, c'est une valeur métier). Renvoie ``(schema, rows)``.
    """
    from .capi_crm import _sha256

    contacts = list(contacts or [])
    has_value = any(c.get('value') not in (None, '') for c in contacts)
    schema = list(SCHEMA) + ([VALUE_SCHEMA_KEY] if has_value else [])

    rows = []
    for c in contacts:
        email = _normalize_email(c.get('email'))
        phone = _normalize_phone(c.get('telephone'))
        if not email and not phone:
            continue
        row = [
            _sha256(email) if email else '',
            _sha256(phone) if phone else '',
        ]
        if has_value:
            value = c.get('value')
            row.append('' if value in (None, '') else str(value))
        rows.append(row)
    return schema, rows


def session_count(n_rows):
    """Nombre de sessions ≤10 000 nécessaires pour ``n_rows`` lignes."""
    if n_rows <= 0:
        return 0
    return (n_rows + MAX_USERS_PER_SESSION - 1) // MAX_USERS_PER_SESSION


def _chunk(rows, size=MAX_USERS_PER_SESSION):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


# ── Résolution de la connexion / du client Meta ──────────────────────────────

def _client_for(company):
    """Client Meta de la société, ou None si la connexion est absente/inactive
    (le moteur no-ope proprement en amont — jamais d'appel sans token)."""
    from .meta_client import MetaClient
    from .models import MetaConnection
    conn = MetaConnection.objects.filter(company=company).first()
    if conn is None or not conn.is_live:
        return None
    return MetaClient.from_connection(conn)


def _upload_rows(client, audience_id, schema, rows, *, replace=True):
    """Téléverse ``rows`` (déjà hachées) par sessions ≤10 000. ``replace=True``
    → ``usersreplace`` sur TOUTE la session (remplacement ATOMIQUE : chaque
    batch de la même session_id contribue, le remplacement s'applique au dernier
    batch — ``last_batch_flag``). Renvoie le nombre de lignes envoyées."""
    import uuid

    chunks = list(_chunk(rows))
    total = len(chunks)
    # session_id unique et stable pour l'ensemble de la session multi-batch.
    session_id = uuid.uuid4().int % (10 ** 15)
    sent = 0
    for seq, chunk in enumerate(chunks, start=1):
        session = {
            'session_id': session_id,
            'batch_seq': seq,
            'last_batch_flag': seq == total,
            'estimated_num_total': len(rows),
        }
        client.add_users_to_audience(
            audience_id=audience_id, schema=schema, data=chunk,
            session=session, replace=replace)
        sent += len(chunk)
    return sent


# ── ADSDEEP57 — [GATED consentement] Custom Audience depuis le CRM ───────────

def sync_crm_custom_audience(company, *, name, contacts, replace=True,
                             description='', client=None):
    """ADSDEEP57 — Synchronise une Custom Audience depuis des contacts CRM.

    ``contacts`` : liste de dicts ``{'email', 'telephone', 'value'?}`` (lus par
    l'appelant via ``apps.crm.selectors`` — jamais un import de ``crm.models``).
    Hache SHA-256 CÔTÉ SERVEUR, découpe en sessions ≤10 000, crée l'audience puis
    la peuple (``usersreplace`` atomique si ``replace``, sinon ``users``).

    GATE : si ``custom_audience_consent_enabled()`` est faux, AUCUN appel réseau
    n'est émis — la fonction renvoie quand même le résumé (compteurs hachés
    localement) pour la préviz UI, ``configured=False``. Renvoie ::

        {'configured', 'name', 'total_contacts', 'matched_rows', 'sessions',
         'schema', 'audience_id', 'sent', 'tos_url', 'error'?}
    """
    schema, rows = build_upload(contacts)
    summary = {
        'configured': custom_audience_consent_enabled(),
        'name': name,
        'total_contacts': len(list(contacts or [])),
        'matched_rows': len(rows),
        'sessions': session_count(len(rows)),
        'schema': schema,
        'audience_id': '',
        'sent': 0,
        'tos_url': CUSTOM_AUDIENCE_TOS_URL,
    }
    # ── PORTE : consentement OFF ⇒ strictement AUCUN réseau ──────────────────
    if not summary['configured']:
        return summary

    client = client or _client_for(company)
    if client is None:
        summary['error'] = 'no_connection'
        return summary

    from .meta_client import MetaError
    try:
        created = client.create_custom_audience(
            name=name, customer_file_source='USER_PROVIDED_ONLY',
            description=description)
        summary['audience_id'] = str((created or {}).get('id') or '')
        if summary['audience_id'] and rows:
            summary['sent'] = _upload_rows(
                client, summary['audience_id'], schema, rows, replace=replace)
    except MetaError as exc:
        summary['error'] = str(exc)[:255]
    except Exception as exc:  # noqa: BLE001 — jamais casser l'appelant
        summary['error'] = str(exc)[:255]
    return summary


def delete_crm_custom_audience(company, audience_id, *, client=None):
    """ADSDEEP57 — Supprime une Custom Audience. GATE identique : consentement
    OFF ⇒ aucun appel réseau (``{'configured': False}``)."""
    if not custom_audience_consent_enabled():
        return {'configured': False, 'deleted': False}
    client = client or _client_for(company)
    if client is None:
        return {'configured': True, 'deleted': False, 'error': 'no_connection'}
    from .meta_client import MetaError
    try:
        client.delete_custom_audience(audience_id=audience_id)
        return {'configured': True, 'deleted': True,
                'audience_id': str(audience_id)}
    except MetaError as exc:
        return {'configured': True, 'deleted': False, 'error': str(exc)[:255]}


# ── ADSDEEP58 — [GATED consentement] Lookalikes (@after 57) ──────────────────

def _clamp_ratio(ratio):
    """Borne le ratio du lookalike à la plage MA 1-5 % (dossier §2)."""
    try:
        ratio = float(ratio)
    except (TypeError, ValueError):
        ratio = MA_LOOKALIKE_MAX_RATIO
    return max(MA_LOOKALIKE_MIN_RATIO, min(MA_LOOKALIKE_MAX_RATIO, ratio))


def create_lookalike_from_seed(company, *, name, origin_audience_id,
                               seed_matched_count, ratio=MA_LOOKALIKE_MAX_RATIO,
                               value_based=False, client=None):
    """ADSDEEP58 — Crée un lookalike MA depuis une audience seed (clients signés).

    ``origin_audience_id`` = la Custom Audience seed (ADSDEEP57) déjà peuplée.
    ``seed_matched_count`` = nombre de personnes matchées côté Meta : un lookalike
    exige ≥100 matchés (dossier §1/§2) — l'UI l'annonce, et on refuse en amont si
    le seuil n'est pas atteint (``seed_sufficient=False``, aucun appel réseau).
    ``ratio`` borné à la plage MA 1-5 %. ``value_based`` → le seed porte une
    colonne ``LOOKALIKE_VALUE`` (montant du devis) et le spec passe en
    ``type=custom_ratio`` (dossier §2).

    GATE : consentement OFF ⇒ AUCUN appel réseau (résumé de préviz seul). Renvoie
    ``{'configured', 'name', 'origin_audience_id', 'seed_matched_count',
    'min_seed', 'seed_sufficient', 'ratio', 'value_based', 'audience_id',
    'error'?}``.
    """
    ratio = _clamp_ratio(ratio)
    seed_matched_count = int(seed_matched_count or 0)
    summary = {
        'configured': custom_audience_consent_enabled(),
        'name': name,
        'origin_audience_id': str(origin_audience_id or ''),
        'seed_matched_count': seed_matched_count,
        'min_seed': LOOKALIKE_MIN_SEED,
        'seed_sufficient': seed_matched_count >= LOOKALIKE_MIN_SEED,
        'ratio': ratio,
        'value_based': bool(value_based),
        'audience_id': '',
    }
    # Seed trop petit → refus AVANT tout réseau (l'UI a déjà annoncé le seuil).
    if not summary['seed_sufficient']:
        summary['error'] = 'seed_too_small'
        return summary
    # ── PORTE : consentement OFF ⇒ strictement AUCUN réseau ──────────────────
    if not summary['configured']:
        return summary
    client = client or _client_for(company)
    if client is None:
        summary['error'] = 'no_connection'
        return summary

    spec = {
        'origin_audience_id': summary['origin_audience_id'],
        'country': 'MA',
        'ratio': ratio,
    }
    if value_based:
        # Lookalike value-based (dossier §2) : le seed est is_value_based, le
        # spec optimise sur la valeur client (custom_ratio).
        spec['type'] = 'custom_ratio'

    from .meta_client import MetaError
    try:
        created = client.create_lookalike_audience(
            name=name, lookalike_spec=spec)
        summary['audience_id'] = str((created or {}).get('id') or '')
    except MetaError as exc:
        summary['error'] = str(exc)[:255]
    except Exception as exc:  # noqa: BLE001 — jamais casser l'appelant
        summary['error'] = str(exc)[:255]
    return summary


def lookalike_delivery_status(company, audience_id, *, client=None):
    """ADSDEEP58 — Poll l'état de préparation d'un lookalike (``delivery_status``/
    ``operation_status`` — prêt en ~1-6 h, dossier §2). LECTURE SEULE, aucune
    donnée CRM envoyée ; gaté sur le même consentement (poller un lookalike qui
    n'aurait jamais pu être créé sans consentement n'a pas de sens). Renvoie
    ``{'configured', 'audience_id', 'operation_status', 'delivery_status',
    'approximate_count', 'ready'}``."""
    if not custom_audience_consent_enabled():
        return {'configured': False}
    client = client or _client_for(company)
    if client is None:
        return {'configured': True, 'error': 'no_connection'}
    from .meta_client import MetaError
    try:
        data = client.get_audience(audience_id)
    except MetaError as exc:
        return {'configured': True, 'audience_id': str(audience_id),
                'error': str(exc)[:255]}
    op = data.get('operation_status') or {}
    delivery = data.get('delivery_status') or {}
    # Code 200 côté Meta = « Normal / ready » ; sinon en préparation.
    ready = str(op.get('code')) == '200' and str(delivery.get('code')) == '200'
    return {
        'configured': True,
        'audience_id': str(audience_id),
        'operation_status': op,
        'delivery_status': delivery,
        'approximate_count': data.get('approximate_count_lower_bound'),
        'ready': ready,
    }


# ── ADSDEEP59 — Audiences d'engagement (NON gated : aucune donnée CRM) ────────
# Objets purement Meta-side : les interactions (formulaire/Page/IG) vivent déjà
# côté Meta, rien n'est envoyé depuis le CRM → pas de consentement 1st-party.
_DAY_SECONDS = 86400

# Rétentions dossier §3 : formulaires lead 90 j ; Page / IG 730 j.
ENGAGEMENT_PRESETS = {
    'lead_opened': {
        'label': 'Formulaire ouvert (non soumis)',
        'source_type': 'lead',
        'event': 'lead_generation_opened',
        'retention_days': 90,
    },
    'lead_dropoff': {
        'label': 'Formulaire abandonné',
        'source_type': 'lead',
        'event': 'lead_generation_dropoff',
        'retention_days': 90,
    },
    'lead_submitted': {
        'label': 'Formulaire soumis',
        'source_type': 'lead',
        'event': 'lead_generation_submitted',
        'retention_days': 90,
    },
    'page_engaged': {
        'label': 'A interagi avec la Page',
        'source_type': 'page',
        'event': 'page_engaged',
        'retention_days': 730,
    },
    'ig_engaged': {
        'label': 'A interagi avec le compte Instagram',
        'source_type': 'ig_business',
        'event': 'ig_business_profile_engaged',
        'retention_days': 730,
    },
}


def engagement_preset_catalog():
    """ADSDEEP59 — Catalogue des audiences d'engagement (pour le picker du
    composeur d'adset). Aucune donnée CRM — objets Meta-side. Expose la rétention
    (dossier §3) pour que l'UI l'affiche avant usage."""
    return [
        {
            'key': key,
            'label': preset['label'],
            'source_type': preset['source_type'],
            'event': preset['event'],
            'retention_days': preset['retention_days'],
        }
        for key, preset in ENGAGEMENT_PRESETS.items()
    ]


def _engagement_rule(preset, source_id):
    """Construit la ``rule`` d'engagement (event_sources typé + rétention +
    filtre sur l'événement)."""
    return {
        'inclusions': {
            'operator': 'or',
            'rules': [{
                'event_sources': [{
                    'type': preset['source_type'],
                    'id': str(source_id),
                }],
                'retention_seconds': preset['retention_days'] * _DAY_SECONDS,
                'filter': {
                    'operator': 'and',
                    'filters': [{
                        'field': 'event',
                        'operator': 'eq',
                        'value': preset['event'],
                    }],
                },
            }],
        },
    }


def _default_source_id(client, source_type):
    """Source par défaut d'un preset d'engagement, résolue depuis la connexion :
    ``ig_user_id`` pour IG, ``page_id`` pour la Page ET les formulaires lead (les
    lead forms vivent sous la Page)."""
    if source_type == 'ig_business':
        return getattr(client, 'ig_user_id', None)
    return getattr(client, 'page_id', None)


def create_engagement_audience(company, *, preset_key, name=None,
                               source_id=None, client=None):
    """ADSDEEP59 — Crée une audience d'engagement. NON gated : AUCUNE donnée CRM
    n'est envoyée (l'audience dérive des interactions déjà côté Meta).

    ``preset_key`` ∈ :data:`ENGAGEMENT_PRESETS`. ``source_id`` (id de Page / lead
    form / compte IG) est résolu depuis la connexion si absent. Renvoie
    ``{'preset', 'audience_id', 'retention_days', 'error'?}``."""
    preset = ENGAGEMENT_PRESETS.get(preset_key)
    if preset is None:
        raise ValueError(f"Preset d'engagement inconnu : {preset_key}")

    client = client or _client_for(company)
    if client is None:
        return {'preset': preset_key, 'audience_id': '',
                'error': 'no_connection'}
    src = source_id or _default_source_id(client, preset['source_type'])
    if not src:
        return {'preset': preset_key, 'audience_id': '', 'error': 'no_source'}

    from .meta_client import MetaError
    rule = _engagement_rule(preset, src)
    audience_name = name or f"Engagement — {preset['label']}"
    try:
        created = client.create_engagement_audience(
            name=audience_name, rule=rule)
        return {
            'preset': preset_key,
            'audience_id': str((created or {}).get('id') or ''),
            'retention_days': preset['retention_days'],
        }
    except MetaError as exc:
        return {'preset': preset_key, 'audience_id': '',
                'error': str(exc)[:255]}


def engagement_delivery_estimate(company, *, targeting_spec,
                                 optimization_goal='REACH', client=None):
    """ADSDEEP59 — Estimation d'audience AVANT usage (dossier §5) — montrée dans
    le picker avant de créer/utiliser une audience. LECTURE SEULE, aucune donnée
    CRM. Renvoie ``{'estimate': {...}}`` ou ``{'error': ...}``."""
    client = client or _client_for(company)
    if client is None:
        return {'error': 'no_connection'}
    from .meta_client import MetaError
    try:
        estimate = client.get_delivery_estimate(
            targeting_spec=targeting_spec, optimization_goal=optimization_goal)
        return {'estimate': estimate}
    except MetaError as exc:
        return {'error': str(exc)[:255]}


# ── PUB58 — Boucles de croissance ERP : PREMIER appelant production d'ADSDEEP57
# (le mécanisme dormait à zéro appelant) ─────────────────────────────────────

def sync_devis_view_audiences(company, *, client=None):
    """PUB58 — Pousse les 2 Custom Audiences « devis vu / jamais ouvert »
    depuis le view-tracking ``ShareLink`` (QJ1,
    ``apps.ventes.selectors.devis_view_tracking_segments``) — PREMIER
    appelant production de :func:`sync_crm_custom_audience` (ADSDEEP57).
    Chaque segment porte un angle de relance dédié (jamais ouvert vs objection
    prix) dans son ``name``/``description``. Même porte consentement : OFF ⇒
    no-op propre (résumés de préviz seuls, aucun réseau). Renvoie
    ``{'jamais_ouvert': <résumé>, 'ouvert_non_signe': <résumé>}``."""
    from apps.ventes.selectors import devis_view_tracking_segments

    segments = devis_view_tracking_segments(company)
    return {
        'jamais_ouvert': sync_crm_custom_audience(
            company, name='Devis jamais ouvert',
            contacts=segments['jamais_ouvert'],
            description='Devis envoyé jamais consulté — relance découverte.',
            client=client),
        'ouvert_non_signe': sync_crm_custom_audience(
            company, name='Devis ouvert non signé',
            contacts=segments['ouvert_non_signe'],
            description=("Devis consulté non signé — objection prix "
                         "probable."),
            client=client),
    }


# ── PUB59 — Audience « devis expiré » ─────────────────────────────────────────

def sync_expired_devis_audience(company, *, client=None):
    """PUB59 — Pousse la Custom Audience « devis expiré »
    (``apps.ventes.selectors.expired_devis_contacts`` — exclusions déjà
    signées appliquées en amont). Angle : « votre prix était valable 30 j,
    nouvelle offre » — l'angle-offre précis que la nurture générique rate.
    Même porte consentement que :func:`sync_crm_custom_audience`."""
    from apps.ventes.selectors import expired_devis_contacts

    contacts = expired_devis_contacts(company)
    return sync_crm_custom_audience(
        company, name='Devis expiré', contacts=contacts,
        description=("Devis expiré — votre prix était valable 30 j, "
                     "nouvelle offre."),
        client=client)
