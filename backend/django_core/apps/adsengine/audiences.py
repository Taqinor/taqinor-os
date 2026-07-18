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
