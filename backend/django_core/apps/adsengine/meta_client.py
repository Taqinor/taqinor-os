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

import json
import time

import httpx

# Version figée de l'API Marketing (recherche 16/07 : v25). SOURCE UNIQUE :
# ADSENG2 l'a extraite dans ``api_version`` (plain-constant, sans dépendance)
# pour que l'émetteur CAPI côté ventes partage EXACTEMENT la même version — plus
# jamais deux littéraux divergents. Ré-exportée ici pour les importeurs existants.
from .api_version import GRAPH_BASE_URL, GRAPH_VERSION  # noqa: F401

# Statut FORCÉ de toute création — codé en dur, jamais surchargeable.
FORCED_STATUS = 'PAUSED'

# ── ADSDEEP4 — Fenêtres d'attribution, SOURCE UNIQUE ─────────────────────────
# ``action_attribution_windows`` demandé sur chaque pull d'insights de
# conversion. Les fenêtres VIVANTES au 2026-07 (dossier insights-api §4). Les
# fenêtres ``7d_view`` et ``28d_view`` sont MORTES depuis 2026-01-12 : les
# demander renvoie SILENCIEUSEMENT aucune donnée (aucune erreur Graph) — donc
# jamais les coder. Un test-garde (``test_attribution_windows``) échoue si l'une
# d'elles réapparaît quelque part dans ce module.
ATTRIBUTION_WINDOWS = ('1d_click', '7d_click', '1d_view')

# Fenêtres INTERDITES (mortes en silence) — listées pour la garde uniquement,
# jamais émises.
DEAD_ATTRIBUTION_WINDOWS = ('7d_view', '28d_view')


# ── Taxonomie d'erreurs ──────────────────────────────────────────────────────
# ── ADSDEEP5 — Budgeteur de rate-limit ───────────────────────────────────────
# Seuil (%) d'utilisation au-delà duquel on RALENTIT la boucle AVANT de heurter
# l'erreur 613 (BUC compte). Meta scale les limites au spend : un petit compte
# atteint vite le plafond, d'où un backoff préventif plutôt que réactif.
THROTTLE_SLOWDOWN_PCT = 90.0
# Pause (s) injectée avant une requête quand l'usage connu franchit le seuil.
THROTTLE_SLEEP_SECONDS = 2.0
# Préfixe de clé de cache où l'état d'usage le plus récent est mémorisé PAR
# compte (lu par ``wiring-health`` — le client vit le temps d'une synchro).
THROTTLE_CACHE_PREFIX = 'adsengine-throttle'
THROTTLE_CACHE_TTL = 3600  # 1 h — au-delà l'info est périmée (fenêtre BUC = 1 h)


def _to_pct(value):
    """Convertit une valeur d'en-tête en float (%), ou None si illisible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_usage_headers(headers):
    """ADSDEEP5 — Extrait l'état d'usage des en-têtes de rate-limit Meta.

    Lit ``X-FB-Ads-Insights-Throttle`` (``app_id_util_pct``/``acc_id_util_pct``/
    ``ads_api_access_tier``), ``X-Ad-Account-Usage`` (``acc_id_util_pct``) et
    ``X-Business-Use-Case-Usage`` (par type : ``call_count``/``total_cputime``/
    ``total_time``/``estimated_time_to_regain_access``). Renvoie un dict
    ``{usage_pct, insights_throttle, account_usage, buc, tier}`` où ``usage_pct``
    est le MAX de tous les pourcentages connus (le budget le plus contraint).
    Robuste à un en-tête absent ou à un JSON illisible (ignoré)."""
    import json as _json

    headers = headers or {}
    pcts = []
    insights_throttle = {}
    account_usage = {}
    buc = {}
    tier = ''

    raw_throttle = headers.get('X-FB-Ads-Insights-Throttle')
    if raw_throttle:
        try:
            insights_throttle = _json.loads(raw_throttle) or {}
        except (ValueError, TypeError):
            insights_throttle = {}
        for key in ('app_id_util_pct', 'acc_id_util_pct'):
            p = _to_pct(insights_throttle.get(key))
            if p is not None:
                pcts.append(p)
        tier = insights_throttle.get('ads_api_access_tier', '') or ''

    raw_acct = headers.get('X-Ad-Account-Usage')
    if raw_acct:
        try:
            account_usage = _json.loads(raw_acct) or {}
        except (ValueError, TypeError):
            account_usage = {}
        p = _to_pct(account_usage.get('acc_id_util_pct'))
        if p is not None:
            pcts.append(p)

    raw_buc = headers.get('X-Business-Use-Case-Usage')
    if raw_buc:
        try:
            buc = _json.loads(raw_buc) or {}
        except (ValueError, TypeError):
            buc = {}
        for entries in (buc or {}).values():
            for entry in (entries or []):
                if not isinstance(entry, dict):
                    continue
                for key in ('call_count', 'total_cputime', 'total_time'):
                    p = _to_pct(entry.get(key))
                    if p is not None:
                        pcts.append(p)

    return {
        'usage_pct': max(pcts) if pcts else None,
        'insights_throttle': insights_throttle,
        'account_usage': account_usage,
        'buc': buc,
        'tier': tier,
    }


def rate_limit_status(ad_account_id):
    """ADSDEEP5 — État d'usage rate-limit mémorisé pour un compte (lu par
    ``wiring-health``). Renvoie ``{usage_pct, tier, throttled}`` ou ``None`` si
    aucune réponse récente n'a été observée. ``throttled`` = usage ≥ seuil."""
    if not ad_account_id:
        return None
    try:
        from django.core.cache import cache
        state = cache.get(f'{THROTTLE_CACHE_PREFIX}:{ad_account_id}')
    except Exception:  # noqa: BLE001 — cache indisponible
        return None
    if not state:
        return None
    pct = state.get('usage_pct')
    return {
        'usage_pct': pct,
        'tier': state.get('tier', ''),
        'throttled': bool(pct is not None and pct >= THROTTLE_SLOWDOWN_PCT),
    }


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
        # ADSDEEP5 — état d'usage rate-limit le plus récent (rempli à chaque
        # réponse). ``usage_pct`` guide le backoff préventif AVANT le 613.
        self.usage_state = {}

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

    def _maybe_throttle(self):
        """ADSDEEP5 — Backoff PRÉVENTIF : si le dernier usage connu franchit le
        seuil, on dort brièvement AVANT la requête (évite de heurter le 613)."""
        pct = (self.usage_state or {}).get('usage_pct')
        if pct is not None and pct >= THROTTLE_SLOWDOWN_PCT:
            if THROTTLE_SLEEP_SECONDS:
                time.sleep(THROTTLE_SLEEP_SECONDS)

    def _record_usage(self, resp):
        """Mémorise l'état d'usage des en-têtes de la réponse (sur l'instance +
        cache par compte pour ``wiring-health``). Best-effort, jamais bloquant."""
        try:
            state = parse_usage_headers(getattr(resp, 'headers', {}) or {})
        except Exception:  # noqa: BLE001 — l'usage n'empêche jamais la requête
            return
        if state.get('usage_pct') is None and not state.get('insights_throttle'):
            return
        self.usage_state = state
        if not self.ad_account_id:
            return
        try:
            from django.core.cache import cache
            cache.set(
                f'{THROTTLE_CACHE_PREFIX}:{self.ad_account_id}',
                state, THROTTLE_CACHE_TTL)
        except Exception:  # noqa: BLE001 — cache indisponible : no-op
            pass

    def _request(self, method, path, *, params=None, data=None):
        url = f'{self._base_url}/{path.lstrip("/")}'
        # Token dans l'en-tête (jamais dans l'URL) : aucun secret en query string.
        headers = {'Authorization': f'Bearer {self._token}'}
        attempt = 0
        while True:
            attempt += 1
            self._maybe_throttle()
            try:
                resp = self._client.request(
                    method, url, params=params, data=data, headers=headers)
            except httpx.TransportError as exc:
                if attempt <= self._max_retries:
                    self._sleep(attempt)
                    continue
                raise MetaError(f'Erreur réseau Meta : {exc}') from exc
            self._record_usage(resp)
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
    # Champs demandés PAR DÉFAUT à l'API Graph pour la synchro des miroirs.
    # SANS ``fields`` explicite, un edge Graph ne renvoie que ``id`` — d'où des
    # miroirs sans nom/statut/objectif/budget (colonnes vides à l'écran). On
    # demande donc exactement ce que ``sync.py`` exploite pour chaque niveau.
    CAMPAIGN_SYNC_FIELDS = (
        'id', 'name', 'status', 'effective_status', 'objective',
        'daily_budget', 'lifetime_budget')
    ADSET_SYNC_FIELDS = (
        'id', 'name', 'status', 'effective_status', 'campaign_id',
        'daily_budget', 'lifetime_budget')
    AD_SYNC_FIELDS = ('id', 'name', 'status', 'effective_status', 'adset_id')

    def get_account(self, *, fields=None):
        """Nœud du compte publicitaire (LECTURE) — ex. sa devise (``currency``,
        ISO-4217) : Meta rapporte TOUS les montants dans la devise du compte."""
        if not self.ad_account_id:
            raise MetaError("ad_account_id manquant sur la connexion Meta.")
        acct = self.ad_account_id
        if not str(acct).startswith('act_'):
            acct = f'act_{acct}'
        payload = self._request(
            'GET', acct, params={'fields': ','.join(fields or ('currency',))})
        return payload if isinstance(payload, dict) else {}

    def get_campaigns(self, *, fields=None, limit=None):
        return self._read_list(self._account_edge('campaigns'),
                               fields=fields or self.CAMPAIGN_SYNC_FIELDS,
                               limit=limit)

    def get_adsets(self, *, fields=None, limit=None):
        return self._read_list(self._account_edge('adsets'),
                               fields=fields or self.ADSET_SYNC_FIELDS,
                               limit=limit)

    def get_ads(self, *, fields=None, limit=None):
        return self._read_list(self._account_edge('ads'),
                               fields=fields or self.AD_SYNC_FIELDS,
                               limit=limit)

    def get_insights(self, object_id, *, fields=None, params=None):
        """Insights d'un objet (compte/campagne/adset/ad). Renvoie la liste
        ``data`` COMPLÈTE (toutes les pages), jamais ``None``."""
        query = dict(params or {})
        if fields:
            query['fields'] = ','.join(fields)
        return self._paged(f'{object_id}/insights', params=query)

    # ── Créatif LIVE (ADSDEEP11/12/13) ───────────────────────────────────────
    # Sous-champs du nœud ``creative`` demandés pour miroiter le créatif diffusé
    # (dossier creative-retrieval §1). ``body`` n'est PAS peuplé pour les vidéos
    # → on lit aussi ``object_story_spec``/``asset_feed_spec``.
    CREATIVE_SUBFIELDS = (
        'id', 'body', 'title', 'description', 'call_to_action_type',
        'image_hash', 'video_id', 'thumbnail_url', 'image_url',
        'instagram_permalink_url', 'effective_object_story_id',
        'object_story_spec', 'asset_feed_spec')

    def get_ad_creative(self, ad_id):
        """ADSDEEP11 — Lit le nœud ``creative{…}`` d'une ad (le créatif LIVE).
        Renvoie le dict ``creative`` (ou ``{}``)."""
        sub = '{' + ','.join(self.CREATIVE_SUBFIELDS) + '}'
        payload = self._request(
            'GET', f'{ad_id}', params={'fields': f'creative{sub}'})
        creative = (payload or {}).get('creative')
        return creative if isinstance(creative, dict) else {}

    def get_video_source(self, video_id):
        """ADSDEEP12 — URL mp4 CDN JOUABLE d'une vidéo (``source``). EXPIRE
        ~1 h : ne JAMAIS la persister — refetch à l'affichage (cache court)."""
        payload = self._request(
            'GET', f'{video_id}',
            params={'fields': 'source,picture,length,permalink_url'})
        return payload if isinstance(payload, dict) else {}

    def get_ad_image(self, image_hash):
        """ADSDEEP12 — Métadonnées d'image par hash ; ``permalink_url`` est la
        seule URL PERMANENTE utilisable pour l'affichage (``url``/``url_128``
        sont temporaires)."""
        if not self.ad_account_id:
            raise MetaError("ad_account_id manquant sur la connexion Meta.")
        payload = self._request(
            'GET', self._account_edge('adimages'),
            params={'hashes': json.dumps([image_hash]),
                    'fields': 'hash,url,url_128,permalink_url,name,width,height'})
        data = (payload or {}).get('data') or []
        return data[0] if data else {}

    def get_ad_previews(self, ad_id, ad_format):
        """ADSDEEP13 — Snippet iframe d'aperçu Meta pour un format. L'iframe
        n'est valide que 24 h → jamais persister, refetch par affichage."""
        rows = self._paged(
            f'{ad_id}/previews', params={'ad_format': ad_format})
        return rows[0].get('body', '') if rows else ''

    def _read_list(self, path, *, fields=None, limit=None):
        params = {}
        if fields:
            params['fields'] = ','.join(fields)
        if limit is not None:
            params['limit'] = limit
        return self._paged(path, params=params or None)

    def _paged(self, path, *, params=None):
        """Suit la pagination Graph (curseur ``paging.cursors.after``) et
        concatène TOUTES les pages. Sans cela, seule la 1re page (~25 lignes) est
        lue → dépense TRONQUÉE dès qu'un objet a un historique long (insights
        ventilés par jour sur plusieurs mois : ex. 600 $ affichés au lieu du
        total réel). Le curseur voyage en paramètre ``after`` (jamais l'URL
        ``next`` renvoyée par Graph, qui embarque le token en clair). Borne dure
        anti-boucle."""
        rows = []
        base = dict(params or {})
        after = None
        for _ in range(1000):  # borne dure (~25k lignes) — jamais infini
            query = dict(base)
            if after:
                query['after'] = after
            payload = self._request('GET', path, params=query or None)
            if not isinstance(payload, dict):
                break
            rows.extend(payload.get('data', []) or [])
            paging = payload.get('paging') or {}
            after = (paging.get('cursors') or {}).get('after')
            if not after or not paging.get('next'):
                break
        return rows

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

    def create_ad_with_object_story_spec(self, *, name, adset_id,
                                         object_story_spec, extra_fields=None):
        """ADSENG30 — Crée une ad « style post » via ``object_story_spec``.

        Un ad ``object_story_spec`` (message + ``page_id``) fait créer par Meta
        le post sous-jacent EN EFFET DE BORD — c'est le chemin des tests type
        « boosted post », ENTIÈREMENT dans le scope ``ads_management`` existant
        (PAS de nouvelle App Review). La publication ORGANIQUE
        (``pages_manage_posts``) reste GATED / hors périmètre : cette méthode ne
        publie AUCUN contenu organique, elle crée un ad.

        INVARIANT PERMANENT (règle #3) : comme toutes les méthodes de création,
        elle n'accepte AUCUN ``status`` (le passer lève ``TypeError``) et FORCE
        ``status=PAUSED`` via ``_forced_status_payload`` (mot final, même défense
        en profondeur) — jamais un chemin qui puisse créer un objet ACTIF. Le
        ``object_story_spec`` est encodé JSON dans le champ ``creative`` (les
        objets imbriqués voyagent en JSON dans les paramètres de formulaire Meta).
        """
        base = {
            'name': name,
            'adset_id': adset_id,
            'creative': json.dumps({'object_story_spec': object_story_spec}),
        }
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
