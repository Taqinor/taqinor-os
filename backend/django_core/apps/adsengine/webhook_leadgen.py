"""MRY0 (lot A) — État du webhook Meta « leadgen », rendu VISIBLE et réparable.

Module PUR (aucune vue, aucun sérialiseur) : il lit la ``MetaConnection``
EXISTANTE et interroge le Graph API en lecture pour dire POURQUOI aucun lead
temps réel n'arrive. Trois causes possibles, dans l'ordre d'affichage :

  1. l'**app** n'est pas souscrite au champ ``leadgen``
     (``GET /{app_id}/subscriptions``) ;
  2. la **Page** n'est pas abonnée à l'app
     (``GET /{page_id}/subscribed_apps``, lisible seulement avec la permission
     ``pages_manage_metadata``) ;
  3. l'app est absente du **Gestionnaire d'accès aux prospects** de la Page
     (Lead Access Manager) — AUCUNE API publique ne lit cette liste : elle est
     détectée par le SYMPTÔME (aucun ``MetaLeadMirror`` d'origine ``webhook``
     depuis plus de 7 jours) et corrigée par le geste du runbook
     (``docs/crm/arrivee_leads.md``).

Incident fondateur du 03/09/2026 (« lead AZIZ ») : le webhook était muet
depuis 46 h alors que la Page recevait des leads — cause 3. Le câblage a été
réparé à la main le 04/09 ; ce module le rend VISIBLE (tuile de l'écran
Connexion + ``manage.py meta_webhook_status``) et auto-réparable pour la
cause 2 (``abonner_page_leadgen``).

Règles :
  * jamais un token imprimé ni journalisé — on journalise la SOURCE ;
  * jamais une exception levée vers l'appelant : toute panne réseau devient
    un dictionnaire d'état avec ``erreur`` renseignée ;
  * version Graph = la source unique ``api_version.GRAPH_BASE_URL``.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.utils import timezone

from .api_version import GRAPH_BASE_URL

logger = logging.getLogger(__name__)

#: URL de callback attendue côté app Meta (la seule que ce dépôt sert).
CALLBACK_URL = 'https://api.taqinor.ma/api/django/crm/webhooks/meta-lead-ads/'

#: Champ webhook attendu.
CHAMP_LEADGEN = 'leadgen'

#: Au-delà de ce silence, on considère le webhook muet (cause 3 probable).
SILENCE_JOURS = 7

_TIMEOUT = 10


def _graph_get(path, params):
    """``GET {GRAPH_BASE_URL}/{path}`` → dict. Lève ``OSError``/``ValueError``
    sur panne (l'appelant les capte) — jamais de token journalisé."""
    url = f'{GRAPH_BASE_URL}/{path}?{urllib.parse.urlencode(params)}'
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def _graph_post(path, params):
    """``POST {GRAPH_BASE_URL}/{path}`` (corps urlencodé) → dict."""
    url = f'{GRAPH_BASE_URL}/{path}'
    data = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def _erreur_graph(exc):
    """Message Meta lisible (jamais le token) depuis une exception urllib."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            payload = json.loads(exc.read().decode('utf-8'))
            err = (payload or {}).get('error') or {}
            message = err.get('message') or str(exc)
            code = err.get('code')
            return f'{message} (code {code})' if code else str(message)
        except Exception:  # noqa: BLE001 — corps illisible
            return f'HTTP {exc.code}'
    return str(exc)


def app_credentials(conn):
    """``(app_id, app_secret)`` de la connexion Meta d'une société.

    Les deux clés sont saisies dans l'écran Connexion du module Publicité
    (``credentials['app_id']`` / ``credentials['app_secret']``). Repli sur
    ``META_LEAD_ADS_APP_SECRET`` (le secret que le webhook utilise déjà pour
    vérifier la signature) quand la connexion ne le porte pas."""
    creds = (getattr(conn, 'credentials', None) or {}) if conn else {}
    app_id = str(creds.get('app_id') or '').strip()
    app_secret = str(creds.get('app_secret') or '').strip()
    if not app_secret:
        app_secret = (
            getattr(settings, 'META_LEAD_ADS_APP_SECRET', '') or '').strip()
    return app_id, app_secret


def _dernier_post_webhook(company):
    """Dernier ``MetaLeadMirror`` posé PAR LE WEBHOOK (origine='webhook')."""
    from .models import MetaLeadMirror

    row = (MetaLeadMirror.objects
           .filter(company=company, origine=MetaLeadMirror.Origine.WEBHOOK)
           .order_by('-created_at').first())
    return getattr(row, 'created_at', None)


def etat_webhook_leadgen(company):
    """État complet du câblage « leadgen » d'une société.

    Renvoie un dict ``{app_id, scopes, token_valide, has_pages_manage_metadata,
    app_subscribed, page_subscribed, dernier_post_webhook, silencieux, ok,
    detail, erreur}``. Ne lève JAMAIS : une panne réseau laisse ``erreur``
    renseignée et ``ok`` faux.
    """
    from .models import MetaConnection
    from .selectors import resolve_lead_ads_access_token

    etat = {
        'app_id': '',
        'scopes': [],
        'token_valide': False,
        'has_pages_manage_metadata': False,
        'app_subscribed': False,
        'page_subscribed': None,
        'page_subscribed_raison': '',
        'dernier_post_webhook': None,
        'silencieux': True,
        'ok': False,
        'detail': '',
        'erreur': '',
    }
    conn = MetaConnection.objects.filter(company=company).first()
    if conn is None:
        etat['detail'] = 'Aucune connexion Meta enregistrée.'
        return etat
    token, source = resolve_lead_ads_access_token(company)
    if not token:
        etat['detail'] = (
            "Aucun jeton d'accès (ni env META_LEAD_ADS_ACCESS_TOKEN, ni "
            'écran Connexion).')
        return etat
    logger.info(
        'adsengine.etat_webhook_leadgen: société %s — jeton via %s',
        getattr(company, 'pk', '?'), source)

    # (1) debug_token — app_id + scopes du jeton (jamais sa valeur).
    try:
        payload = _graph_get('debug_token', {
            'input_token': token, 'access_token': token})
        data = (payload or {}).get('data') or {}
        etat['app_id'] = str(data.get('app_id') or '')
        etat['scopes'] = list(data.get('scopes') or [])
        etat['token_valide'] = bool(data.get('is_valid'))
        etat['has_pages_manage_metadata'] = (
            'pages_manage_metadata' in etat['scopes'])
    except Exception as exc:  # noqa: BLE001 — jamais bloquant
        etat['erreur'] = _erreur_graph(exc)
        etat['detail'] = f'Meta injoignable ({etat["erreur"]}).'
        return etat

    app_id, app_secret = app_credentials(conn)
    app_id = app_id or etat['app_id']
    etat['app_id'] = app_id

    # (2) /{app_id}/subscriptions — l'app écoute-t-elle `leadgen` sur `page` ?
    if app_id and app_secret:
        try:
            payload = _graph_get(f'{app_id}/subscriptions', {
                'access_token': f'{app_id}|{app_secret}'})
            for row in ((payload or {}).get('data') or []):
                if str(row.get('object') or '') != 'page':
                    continue
                champs = {str(f.get('name') or '')
                          for f in (row.get('fields') or [])}
                if CHAMP_LEADGEN not in champs:
                    continue
                if not row.get('active', True):
                    continue
                if str(row.get('callback_url') or '') == CALLBACK_URL:
                    etat['app_subscribed'] = True
                    break
        except Exception as exc:  # noqa: BLE001
            etat['erreur'] = _erreur_graph(exc)
    else:
        etat['erreur'] = (
            "app_id / app_secret absents de l'écran Connexion — "
            "impossible de lire l'abonnement de l'app.")

    # (3) /{page_id}/subscribed_apps — la Page est-elle abonnée à l'app ?
    page_id = str(getattr(conn, 'page_id', '') or '')
    if not page_id:
        etat['page_subscribed_raison'] = 'ID Page absent de la connexion.'
    else:
        try:
            page_token = _page_access_token(page_id, token)
            payload = _graph_get(f'{page_id}/subscribed_apps', {
                'access_token': page_token})
            abonnees = (payload or {}).get('data') or []
            etat['page_subscribed'] = any(
                CHAMP_LEADGEN in {str(f) for f in (row.get(
                    'subscribed_fields') or [])}
                and (not app_id or str(row.get('id') or '') == app_id)
                for row in abonnees)
            if not etat['page_subscribed']:
                etat['page_subscribed_raison'] = (
                    "l'app n'est pas abonnée au champ leadgen de la Page")
        except Exception as exc:  # noqa: BLE001
            etat['page_subscribed'] = None
            message = _erreur_graph(exc)
            if '(#200)' in message or 'code 200' in message:
                etat['page_subscribed_raison'] = (
                    'permission pages_manage_metadata absente — état de la '
                    'Page illisible')
            else:
                etat['page_subscribed_raison'] = message

    # (4) Symptôme — dernier POST webhook reçu.
    dernier = _dernier_post_webhook(company)
    etat['dernier_post_webhook'] = dernier
    if dernier is not None:
        age = (timezone.now() - dernier).days
        etat['silencieux'] = age > SILENCE_JOURS
    etat['ok'] = bool(
        etat['app_subscribed'] and etat['page_subscribed']
        and not etat['silencieux'])
    etat['detail'] = _detail_fr(etat)
    return etat


def _page_access_token(page_id, user_token):
    """Jeton de Page (``GET /{page_id}?fields=access_token``), repli sur le
    jeton system-user quand la Page n'en expose pas."""
    try:
        payload = _graph_get(page_id, {
            'fields': 'access_token', 'access_token': user_token})
        return str((payload or {}).get('access_token') or '') or user_token
    except Exception:  # noqa: BLE001 — repli assumé, l'appel suivant tranchera
        return user_token


def _detail_fr(etat):
    """Phrase FR qui dit exactement quoi faire — jamais un jargon nu."""
    if not etat['token_valide']:
        return "Le jeton d'accès Meta n'est plus valide — le régénérer."
    if not etat['app_subscribed']:
        return (
            "L'app Meta n'écoute pas le champ « leadgen » sur l'objet Page "
            f'(callback attendu : {CALLBACK_URL}).')
    if etat['page_subscribed'] is None:
        raison = etat['page_subscribed_raison'] or 'état illisible'
        return (
            "Impossible de lire l'abonnement de la Page — "
            f'{raison}. Générer un jeton portant pages_manage_metadata.')
    if not etat['page_subscribed']:
        return (
            "La Page n'est pas abonnée à l'app — bouton « Abonner la Page » "
            'ci-dessous.')
    if etat['silencieux']:
        return (
            'Câblage complet mais AUCUN lead reçu par le webhook depuis plus '
            f'de {SILENCE_JOURS} jours : vérifier le Gestionnaire d\'accès aux '
            "prospects de la Page (Paramètres → Intégrations → Accès aux "
            "prospects → CRM → « Affecter le CRM » → l'app).")
    return 'Leads Meta reçus en temps réel.'


def abonner_page_leadgen(company):
    """``POST /{page_id}/subscribed_apps`` avec ``subscribed_fields=leadgen``.

    Renvoie ``{ok, detail}`` ; l'erreur Meta est renvoyée TELLE QUELLE, jamais
    levée (l'écran Connexion l'affiche à Reda mot pour mot)."""
    from .models import MetaConnection
    from .selectors import resolve_lead_ads_access_token

    conn = MetaConnection.objects.filter(company=company).first()
    if conn is None:
        return {'ok': False, 'detail': 'Aucune connexion Meta enregistrée.'}
    page_id = str(getattr(conn, 'page_id', '') or '')
    if not page_id:
        return {'ok': False, 'detail': "ID Page absent de la connexion."}
    token, source = resolve_lead_ads_access_token(company)
    if not token:
        return {'ok': False, 'detail': "Aucun jeton d'accès Meta."}
    logger.info(
        'adsengine.abonner_page_leadgen: société %s — jeton via %s',
        getattr(company, 'pk', '?'), source)
    try:
        page_token = _page_access_token(page_id, token)
        payload = _graph_post(f'{page_id}/subscribed_apps', {
            'subscribed_fields': CHAMP_LEADGEN, 'access_token': page_token})
    except Exception as exc:  # noqa: BLE001 — l'erreur Meta remonte en texte
        return {'ok': False, 'detail': _erreur_graph(exc)}
    if (payload or {}).get('success'):
        return {'ok': True, 'detail': 'Page abonnée au champ leadgen.'}
    return {'ok': False, 'detail': json.dumps(payload or {}, ensure_ascii=False)}
