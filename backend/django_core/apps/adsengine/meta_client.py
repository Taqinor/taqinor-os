"""ENG4 — Client Meta Marketing API v25 (httpx).

SÉCURITÉ (extension permanente de la règle #3) : toute création de campagne /
adset / ad naît **TOUJOURS** ``status='PAUSED'`` — la valeur est codée EN DUR
dans le corps de chaque méthode de création, jamais un paramètre ni un kwarg par
défaut. Les signatures de création n'acceptent AUCUN ``status`` (le passer lève
``TypeError``, garanti par le langage) et, par défense en profondeur, tout
``status`` glissé via ``extra_fields`` est retiré puis réécrit en ``PAUSED``.

**Aucune méthode d'activation / dé-pause n'existe dans ce client** — c'est
volontaire et vérifié par test. Le token vient de ``MetaConnection.credentials``
(System-User long-lived) et voyage dans l'en-tête ``Authorization: Bearer`` —
jamais dans l'URL (aucune fuite de secret dans les logs/query strings).

Aucune dépendance pip nouvelle : ``httpx`` est déjà épinglé.
"""
from __future__ import annotations

import time

import httpx

# Version figée de l'API Marketing (recherche 16/07 : v25).
GRAPH_VERSION = 'v25.0'
GRAPH_BASE_URL = f'https://graph.facebook.com/{GRAPH_VERSION}'

# Statut FORCÉ de toute création — codé en dur, jamais surchargeable.
FORCED_STATUS = 'PAUSED'


# ── Taxonomie d'erreurs ──────────────────────────────────────────────────────
class MetaError(Exception):
    """Erreur générique côté client Meta (réseau, ou non classée)."""

    def __init__(self, message, *, code=None, subcode=None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


class MetaAuthError(MetaError):
    """Token expiré / invalide / permissions insuffisantes (code 190, HTTP 401)."""


class MetaRateLimitError(MetaError):
    """Limite de débit atteinte (codes 4/17/32/613, HTTP 429) — transitoire."""


class MetaAPIError(MetaError):
    """Autre erreur applicative renvoyée par l'API Meta."""


class MetaClient:
    """Client minimal de l'API Marketing v25.

    LECTURES : campagnes / adsets / ads / insights.
    CRÉATIONS : campagne / adset / ad — TOUJOURS PAUSED, jamais activables.

    Le client est injectable (``http_client=`` un ``httpx.Client``) pour être
    testé sans réseau (``httpx.MockTransport``).
    """

    def __init__(self, *, access_token, ad_account_id=None, page_id=None,
                 base_url=GRAPH_BASE_URL, http_client=None, max_retries=3,
                 backoff_base=0.5):
        if not access_token:
            raise MetaAuthError(
                "Token Meta manquant : connexion non configurée ou désactivée.")
        self._token = access_token
        self.ad_account_id = ad_account_id
        self.page_id = page_id
        self._base_url = base_url.rstrip('/')
        self._client = http_client or httpx.Client(timeout=30.0)
        self._owns_client = http_client is None
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    @classmethod
    def from_connection(cls, connection, **kwargs):
        """Construit un client depuis une ``MetaConnection`` (token write-only).

        Lève ``MetaAuthError`` si aucun ``access_token`` n'est présent — le
        moteur no-ope proprement en amont (jamais d'appel réseau sans token).
        """
        token = (connection.credentials or {}).get('access_token')
        return cls(
            access_token=token,
            ad_account_id=connection.ad_account_id or None,
            page_id=connection.page_id or None,
            **kwargs,
        )

    # ── Transport (retry/backoff + classification d'erreurs) ─────────────────
    def _account_edge(self, edge):
        if not self.ad_account_id:
            raise MetaError("ad_account_id manquant sur la connexion Meta.")
        acct = self.ad_account_id
        if not str(acct).startswith('act_'):
            acct = f'act_{acct}'
        return f'{acct}/{edge}'

    def _sleep(self, attempt):
        if self._backoff_base:
            time.sleep(self._backoff_base * (2 ** (attempt - 1)))

    def _classify(self, resp):
        try:
            error = (resp.json() or {}).get('error', {}) or {}
        except ValueError:
            error = {}
        code = error.get('code')
        subcode = error.get('error_subcode')
        message = error.get('message') or f'HTTP {resp.status_code}'
        if code == 190 or resp.status_code == 401:
            return MetaAuthError(
                f'Token Meta expiré ou invalide : {message}',
                code=code, subcode=subcode)
        if code in (4, 17, 32, 613) or resp.status_code == 429:
            return MetaRateLimitError(
                f'Limite de débit Meta : {message}', code=code, subcode=subcode)
        return MetaAPIError(
            f'Erreur API Meta : {message}', code=code, subcode=subcode)

    def _request(self, method, path, *, params=None, data=None):
        url = f'{self._base_url}/{path.lstrip("/")}'
        # Token dans l'en-tête (jamais dans l'URL) : aucun secret en query string.
        headers = {'Authorization': f'Bearer {self._token}'}
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._client.request(
                    method, url, params=params, data=data, headers=headers)
            except httpx.TransportError as exc:
                if attempt <= self._max_retries:
                    self._sleep(attempt)
                    continue
                raise MetaError(f'Erreur réseau Meta : {exc}') from exc
            if resp.status_code >= 400:
                err = self._classify(resp)
                transient = (
                    isinstance(err, MetaRateLimitError)
                    or resp.status_code >= 500)
                if transient and attempt <= self._max_retries:
                    self._sleep(attempt)
                    continue
                raise err
            try:
                return resp.json()
            except ValueError:
                return {}

    # ── Lectures ─────────────────────────────────────────────────────────────
    def get_campaigns(self, *, fields=None, limit=None):
        return self._read_list(self._account_edge('campaigns'),
                               fields=fields, limit=limit)

    def get_adsets(self, *, fields=None, limit=None):
        return self._read_list(self._account_edge('adsets'),
                               fields=fields, limit=limit)

    def get_ads(self, *, fields=None, limit=None):
        return self._read_list(self._account_edge('ads'),
                               fields=fields, limit=limit)

    def get_insights(self, object_id, *, fields=None, params=None):
        """Insights d'un objet (compte/campagne/adset/ad). Renvoie la liste
        ``data`` parsée (jamais ``None``)."""
        query = dict(params or {})
        if fields:
            query['fields'] = ','.join(fields)
        payload = self._request('GET', f'{object_id}/insights', params=query)
        return payload.get('data', []) if isinstance(payload, dict) else []

    def _read_list(self, path, *, fields=None, limit=None):
        params = {}
        if fields:
            params['fields'] = ','.join(fields)
        if limit is not None:
            params['limit'] = limit
        payload = self._request('GET', path, params=params or None)
        return payload.get('data', []) if isinstance(payload, dict) else []

    # ── Créations (TOUJOURS PAUSED — jamais de kwarg status) ─────────────────
    @staticmethod
    def _forced_status_payload(base, extra_fields):
        """Fusionne ``base`` + ``extra_fields`` puis IMPOSE ``status=PAUSED``.

        Tout ``status`` glissé dans ``extra_fields`` est retiré ; ``PAUSED`` est
        écrit EN DERNIER pour gagner sur toute valeur résiduelle. Défense en
        profondeur : les signatures publiques n'acceptent déjà aucun ``status``.
        """
        payload = dict(base)
        extras = dict(extra_fields or {})
        extras.pop('status', None)
        payload.update(extras)
        payload['status'] = FORCED_STATUS  # codé en dur, mot final
        return payload

    def create_campaign(self, *, name, objective, special_ad_categories=None,
                        extra_fields=None):
        """Crée une campagne — TOUJOURS PAUSED (aucun ``status`` acceptable)."""
        base = {
            'name': name,
            'objective': objective,
            'special_ad_categories': special_ad_categories or [],
        }
        payload = self._forced_status_payload(base, extra_fields)
        return self._request(
            'POST', self._account_edge('campaigns'), data=payload)

    def create_adset(self, *, name, campaign_id, extra_fields=None):
        """Crée un ad set — TOUJOURS PAUSED (aucun ``status`` acceptable)."""
        base = {'name': name, 'campaign_id': campaign_id}
        payload = self._forced_status_payload(base, extra_fields)
        return self._request(
            'POST', self._account_edge('adsets'), data=payload)

    def create_ad(self, *, name, adset_id, extra_fields=None):
        """Crée une ad — TOUJOURS PAUSED (aucun ``status`` acceptable)."""
        base = {'name': name, 'adset_id': adset_id}
        payload = self._forced_status_payload(base, extra_fields)
        return self._request(
            'POST', self._account_edge('ads'), data=payload)

    # ── Mise en pause (PAUSED-only — jamais de kwarg status) ─────────────────
    def update_status_paused(self, *, object_id, level=None):
        """ENGFIX5 — Met un objet (campagne / adset / ad) en ``PAUSED`` — et RIEN
        d'autre. C'est l'action de SÉCURITÉ du moteur (le détecteur d'anomalie et
        le brief hebdo proposent des pauses ; sans cette méthode elles ne peuvent
        pas s'exécuter).

        INVARIANT PERMANENT (règle #3) : la méthode n'accepte AUCUN paramètre
        ``status`` — le passer lève ``TypeError`` (garanti par le langage), comme
        les méthodes de création. Le corps FORCE ``status=PAUSED`` via
        ``_forced_status_payload`` (mot final, même défense en profondeur que les
        créations) : il est impossible d'activer / dé-pauser quoi que ce soit par
        cette méthode. ``level`` (campaign/adset/ad) est purement indicatif
        (journalisation / routing) et n'influence jamais le statut posé."""
        payload = self._forced_status_payload({}, None)
        return self._request('POST', f'{object_id}', data=payload)

    # NOTE : il n'existe DÉLIBÉRÉMENT aucune méthode d'activation / dé-pause /
    # resume / enable. Une campagne ne peut jamais être activée par ce client
    # (règle permanente #3) — vérifié par test. ``update_status_paused`` ne peut,
    # elle, QUE poser PAUSED (aucun status paramétrable).

    # ── Hygiène ──────────────────────────────────────────────────────────────
    def close(self):
        if self._owns_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
