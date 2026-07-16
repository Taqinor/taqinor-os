"""ADSENG-ODOO — Client Odoo JSON-RPC **LECTURE SEULE** (httpx).

Le coût-par-signature du moteur (``metrics.py``) se calcule aujourd'hui contre le
CRM de l'ERP. Or les VRAIES signatures du fondateur vivent dans Odoo Online
(``crm.lead`` gagnés + ``sale.order`` confirmés), pas dans le CRM de l'ERP. Ce
module lit ces deals — et RIEN d'autre.

RÈGLE NON-NÉGOCIABLE #1 (CLAUDE.md) : tout accès Odoo passe par son API JSON
(JSON-RPC), et ce connecteur est **STRICTEMENT LECTURE SEULE**. Il n'appelle
JAMAIS ``create`` / ``write`` / ``unlink`` ni aucune méthode mutante, JAMAIS de
SQL. Défense en profondeur : ``_execute_kw`` refuse (``OdooError``) toute méthode
absente de l'allowlist lecture ``_READ_METHODS`` (``search_read`` / ``read`` /
``search_count`` / ``search`` / ``fields_get``) — un appel d'écriture est
impossible par construction, jamais seulement par convention.

CONFIG PAR ENV (jamais codée en dur) : ``ODOO_URL``, ``ODOO_DB``,
``ODOO_USERNAME`` (le login), ``ODOO_API_KEY`` (la clé d'API Odoo, utilisée comme
mot de passe dans les appels authenticate/execute_kw). Key-gated exactement comme
les fonctionnalités Meta/CAPI : sans les 4 variables, ``is_configured()`` est
faux et TOUTE lecture est un no-op propre renvoyant vide (jamais un 500, jamais un
appel réseau).

Aucune dépendance pip nouvelle : ``httpx`` est déjà épinglé (comme
``meta_client``). Le client est injectable (``http_client=``) pour être testé
sans réseau via ``httpx.MockTransport``.
"""
from __future__ import annotations

import os
import time

import httpx

# Endpoint JSON-RPC standard d'une instance Odoo.
_JSONRPC_PATH = 'jsonrpc'

# Allowlist LECTURE SEULE : les seules méthodes ORM que ``_execute_kw`` accepte.
# Toute autre (create/write/unlink/copy/…) lève ``OdooError`` — garantie
# structurelle qu'aucune écriture Odoo n'est possible via ce client (règle #1).
_READ_METHODS = frozenset({
    'search_read', 'read', 'search_count', 'search', 'fields_get',
})

# Clés d'environnement de configuration (jamais l'URL/db en dur).
ENV_URL = 'ODOO_URL'
ENV_DB = 'ODOO_DB'
ENV_USERNAME = 'ODOO_USERNAME'
ENV_API_KEY = 'ODOO_API_KEY'


# ── Taxonomie d'erreurs (miroir de meta_client) ──────────────────────────────
class OdooError(Exception):
    """Erreur générique côté client Odoo (réseau, RPC, ou méthode non lecture)."""


class OdooAuthError(OdooError):
    """Authentification refusée (uid faux) ou clé d'API invalide/expirée."""


def _setting(name):
    """Valeur d'un réglage (settings Django puis environnement), strip. '' si
    absent — même patron que ``capi_crm._setting``."""
    try:
        from django.conf import settings
        val = getattr(settings, name, None)
    except Exception:  # noqa: BLE001 — utilisable hors contexte Django
        val = None
    return (val or os.environ.get(name, '') or '').strip()


def is_configured():
    """Les 4 variables ODOO_* sont-elles TOUTES posées ? Sans elles, tout le
    connecteur no-ope (aucun appel réseau)."""
    return all(_setting(k) for k in (ENV_URL, ENV_DB, ENV_USERNAME, ENV_API_KEY))


class OdooClient:
    """Client Odoo JSON-RPC minimal, **LECTURE SEULE**.

    Deux services JSON-RPC standard d'Odoo :
      * ``common.authenticate(db, username, api_key, {})`` → ``uid`` (entier) ;
      * ``object.execute_kw(db, uid, api_key, model, method, args, kwargs)`` —
        UNIQUEMENT avec une ``method`` de ``_READ_METHODS``.

    Sans configuration (``is_configured()`` faux), le constructeur classique
    échoue proprement ; préférez ``from_env()`` qui renvoie ``None`` quand le
    connecteur n'est pas configuré (no-op propre en amont).
    """

    def __init__(self, *, url, db, username, api_key, http_client=None,
                 timeout=20.0, max_retries=3, backoff_base=0.5):
        if not (url and db and username and api_key):
            raise OdooError(
                "Connecteur Odoo non configuré (URL/db/username/clé manquants).")
        self._url = url.rstrip('/')
        self._db = db
        self._username = username
        self._api_key = api_key
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._uid = None
        self._rpc_id = 0

    @classmethod
    def from_env(cls, **kwargs):
        """Construit un client depuis les variables ODOO_*, ou ``None`` si le
        connecteur n'est pas configuré (chemin no-op propre — jamais d'appel
        réseau ni d'exception quand les clés manquent)."""
        if not is_configured():
            return None
        return cls(
            url=_setting(ENV_URL), db=_setting(ENV_DB),
            username=_setting(ENV_USERNAME), api_key=_setting(ENV_API_KEY),
            **kwargs)

    # ── Transport JSON-RPC (retry/backoff + classification d'erreurs) ────────
    def _sleep(self, attempt):
        if self._backoff_base:
            time.sleep(self._backoff_base * (2 ** (attempt - 1)))

    def _rpc(self, service, method, args):
        """Un appel JSON-RPC ``{service, method, args}``. Renvoie ``result`` ou
        lève ``OdooAuthError``/``OdooError``. La clé d'API voyage dans le CORPS
        JSON (jamais dans l'URL) — aucun secret en query string."""
        self._rpc_id += 1
        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': {'service': service, 'method': method, 'args': args},
            'id': self._rpc_id,
        }
        url = f'{self._url}/{_JSONRPC_PATH}'
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._client.post(url, json=payload)
            except httpx.TransportError as exc:
                if attempt <= self._max_retries:
                    self._sleep(attempt)
                    continue
                raise OdooError(f'Erreur réseau Odoo : {exc}') from exc
            if resp.status_code >= 500 and attempt <= self._max_retries:
                self._sleep(attempt)
                continue
            if resp.status_code >= 400:
                raise OdooError(f'HTTP {resp.status_code} depuis Odoo.')
            try:
                data = resp.json()
            except ValueError as exc:
                raise OdooError('Réponse Odoo non-JSON.') from exc
            if isinstance(data, dict) and data.get('error'):
                raise self._classify(data['error'])
            return data.get('result') if isinstance(data, dict) else None

    @staticmethod
    def _classify(error):
        """Mappe une erreur JSON-RPC Odoo vers la taxonomie. Une AccessDenied /
        problème d'authentification devient ``OdooAuthError``."""
        message = ''
        blob = ''
        if isinstance(error, dict):
            message = error.get('message') or ''
            data = error.get('data') or {}
            if isinstance(data, dict):
                blob = f"{data.get('name', '')} {data.get('message', '')}"
        haystack = f'{message} {blob}'.lower()
        if ('accessdenied' in haystack or 'access denied' in haystack
                or 'authentication' in haystack or 'invalid' in haystack
                and 'credential' in haystack):
            return OdooAuthError(f'Authentification Odoo refusée : {message}')
        return OdooError(f'Erreur RPC Odoo : {message}')

    def authenticate(self):
        """``common.authenticate`` → uid (mémoïsé). Lève ``OdooAuthError`` si les
        identifiants sont refusés (uid faux). LECTURE : authenticate ne mute
        rien côté Odoo."""
        if self._uid:
            return self._uid
        uid = self._rpc('common', 'authenticate',
                        [self._db, self._username, self._api_key, {}])
        if not uid:
            raise OdooAuthError(
                'Authentification Odoo refusée (uid vide) — vérifiez '
                'ODOO_USERNAME / ODOO_API_KEY / ODOO_DB.')
        self._uid = uid
        return uid

    def _execute_kw(self, model, method, args, kwargs=None):
        """``object.execute_kw`` GARDÉ : ``method`` DOIT appartenir à
        ``_READ_METHODS`` — sinon ``OdooError`` (défense en profondeur règle #1 :
        aucune écriture Odoo possible via ce client). Authentifie au besoin."""
        if method not in _READ_METHODS:
            raise OdooError(
                f"Méthode Odoo « {method} » interdite : connecteur LECTURE "
                f"SEULE (autorisées : {sorted(_READ_METHODS)}).")
        uid = self.authenticate()
        return self._rpc('object', 'execute_kw',
                         [self._db, uid, self._api_key, model, method,
                          args, kwargs or {}])

    def search_read(self, model, domain=None, *, fields=None, limit=None,
                    order=None):
        """``search_read`` LECTURE SEULE : renvoie toujours une liste (jamais
        None). ``domain`` par défaut ``[]`` (tout, aucun filtre utilisateur)."""
        kwargs = {}
        if fields is not None:
            kwargs['fields'] = list(fields)
        if limit is not None:
            kwargs['limit'] = limit
        if order is not None:
            kwargs['order'] = order
        rows = self._execute_kw(model, 'search_read', [domain or []], kwargs)
        return rows if isinstance(rows, list) else []

    def search_count(self, model, domain=None):
        """``search_count`` LECTURE SEULE : nombre d'enregistrements."""
        count = self._execute_kw(model, 'search_count', [domain or []])
        return int(count) if isinstance(count, int) else 0

    # ── Lectures métier ──────────────────────────────────────────────────────
    # Champs lus sur crm.lead (nom encode souvent la campagne/formulaire ;
    # phone/mobile pour le matching ; expected_revenue en repli de montant ;
    # probability/stage_id/date_closed/active pour détecter « gagné » ;
    # user_id = commercial, lu SANS filtre utilisateur, partner_id pour dédup).
    LEAD_FIELDS = (
        'id', 'name', 'phone', 'mobile', 'contact_name', 'partner_name',
        'email_from', 'expected_revenue', 'probability', 'stage_id',
        'user_id', 'partner_id', 'date_closed', 'active', 'create_date',
    )
    # Champs lus sur sale.order (state = signé ; amount_total = montant ;
    # date_order = date ; partner_id pour résoudre le téléphone ;
    # opportunity_id relie la commande au lead d'origine).
    SALE_ORDER_FIELDS = (
        'id', 'name', 'state', 'amount_total', 'date_order', 'partner_id',
        'opportunity_id', 'create_date',
    )
    PARTNER_FIELDS = ('id', 'phone', 'mobile', 'name')

    def read_leads(self, since=None):
        """LECTURE SEULE — tous les ``crm.lead`` (aucun filtre utilisateur : on
        lit TOUS les commerciaux). ``since`` (date/datetime/str) borne
        ``create_date >=``. Renvoie les dicts bruts (champs ``LEAD_FIELDS``)."""
        domain = []
        if since is not None:
            domain.append(['create_date', '>=', _as_odoo_dt(since)])
        return self.search_read(
            'crm.lead', domain, fields=self.LEAD_FIELDS, order='id')

    def read_sale_orders(self, since=None):
        """LECTURE SEULE — tous les ``sale.order``. ``since`` borne
        ``date_order >=``. Renvoie les dicts bruts (champs
        ``SALE_ORDER_FIELDS``)."""
        domain = []
        if since is not None:
            domain.append(['date_order', '>=', _as_odoo_dt(since)])
        return self.search_read(
            'sale.order', domain, fields=self.SALE_ORDER_FIELDS, order='id')

    def read_partners(self, ids):
        """LECTURE SEULE — ``res.partner`` (phone/mobile) pour un ensemble d'ids,
        afin de résoudre le téléphone d'une commande via son ``partner_id``.
        Renvoie ``{id: {'phone', 'mobile', 'name'}}`` ; ``[]`` d'ids → ``{}``."""
        ids = [i for i in (ids or []) if i]
        if not ids:
            return {}
        rows = self.search_read(
            'res.partner', [['id', 'in', ids]], fields=self.PARTNER_FIELDS)
        return {r['id']: r for r in rows if r.get('id')}

    # ── Hygiène ──────────────────────────────────────────────────────────────
    def close(self):
        if self._owns_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _as_odoo_dt(value):
    """Sérialise ``since`` au format datetime Odoo (``YYYY-MM-DD HH:MM:SS``).
    Accepte str (renvoyée telle quelle), date ou datetime."""
    import datetime as _dt
    if isinstance(value, str):
        return value
    if isinstance(value, _dt.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, _dt.date):
        return value.strftime('%Y-%m-%d 00:00:00')
    return str(value)


# NOTE : il n'existe DÉLIBÉRÉMENT aucune méthode create/write/unlink/copy sur ce
# client. ``_execute_kw`` refuse d'ailleurs toute méthode hors ``_READ_METHODS``.
# Le connecteur ne peut, par construction, QUE lire Odoo (règle #1).
