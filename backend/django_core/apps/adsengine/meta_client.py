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

    def _page_edge(self, edge):
        """ADSDEEP49 — Chemin d'un edge de la Page (``<page_id>/<edge>``). Lève si
        la connexion n'a pas de ``page_id`` (aucun appel sur une Page inconnue)."""
        if not self.page_id:
            raise MetaError("page_id manquant sur la connexion Meta.")
        return f'{self.page_id}/{edge}'

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

    def get_ad_leads(self, ad_id, *, since_unix=None):
        """ADSDEEP18 — Leads d'une ad lead-form (``GET /<ad_id>/leads``).

        Renvoie la liste des leads (``id``/``created_time``/``field_data``/
        ``form_id``/``ad_id``). Fenêtre Meta = 90 j (les leads plus anciens sont
        supprimés côté Meta — Odoo est la seule source historique). Filtrage date
        optionnel via ``since_unix`` (``time_created > since``)."""
        params = {
            'fields': 'id,created_time,ad_id,form_id,field_data',
        }
        if since_unix is not None:
            params['filtering'] = json.dumps([{
                'field': 'time_created', 'operator': 'GREATER_THAN',
                'value': int(since_unix)}])
        return self._paged(f'{ad_id}/leads', params=params)

    def get_ad_targeting_ids(self, ad_id):
        """ADSDEEP18 — Résout ``adset_id``/``campaign_id`` d'une ad (le lead ne
        les porte pas — dossier leads-capi §1)."""
        payload = self._request(
            'GET', f'{ad_id}', params={'fields': 'adset_id,campaign_id'})
        if not isinstance(payload, dict):
            return {'adset_id': '', 'campaign_id': ''}
        return {
            'adset_id': str(payload.get('adset_id') or ''),
            'campaign_id': str(payload.get('campaign_id') or ''),
        }

    def get_ad_previews(self, ad_id, ad_format):
        """ADSDEEP13 — Snippet iframe d'aperçu Meta pour un format. L'iframe
        n'est valide que 24 h → jamais persister, refetch par affichage."""
        rows = self._paged(
            f'{ad_id}/previews', params={'ad_format': ad_format})
        return rows[0].get('body', '') if rows else ''

    # ── ADSDEEP49 — Posts ORGANIQUES de Page (lecture + cross-check ads_posts) ─
    # ``application`` permet de déduire ``created_by_app`` côté synchro : l'app ne
    # peut ÉDITER que les posts créés par elle-même (dossier organic-posts §1).
    PAGE_POST_FIELDS = (
        'id', 'message', 'created_time', 'permalink_url', 'is_published',
        'scheduled_publish_time', 'application')

    def get_page_posts(self, *, fields=None, limit=None):
        """ADSDEEP49 — Lit les posts de la Page (``GET /<page_id>/posts``).
        Renvoie la liste COMPLÈTE (toutes les pages, curseur ``after``)."""
        return self._read_list(
            self._page_edge('posts'),
            fields=fields or self.PAGE_POST_FIELDS, limit=limit)

    def get_ads_posts_ids(self):
        """ADSDEEP49 — Ensemble des IDs de TOUS les posts de la Page utilisés en
        ads (dark compris) via ``GET /<page_id>/ads_posts``. Sert au cross-check
        ``ad_linked`` (un post adossé à une pub est risqué à éditer/supprimer —
        dossier organic-posts §1)."""
        rows = self._read_list(self._page_edge('ads_posts'), fields=('id',))
        return {
            str(r.get('id') or '').strip()
            for r in rows or [] if isinstance(r, dict) and r.get('id')}

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

    def duplicate_adset_with_ad(self, *, campaign_id, new_adset_name,
                                new_ad_name, creative_id,
                                adset_extra_fields=None, ad_extra_fields=None):
        """ADSDEEP37 — Duplique un ad set (+ UNE ad qui RÉUTILISE le créatif LIVE
        de la source) : 2 créations en séquence, TOUJOURS PAUSED (aucune des
        deux signatures internes n'accepte de ``status`` — même garantie que
        les créations normales, invariant permanent règle #3).

        ``creative_id`` DOIT venir d'``AdCreativeMirror.creative_meta_id``
        (dossier ADSDEEP11 — un ``AdMirror`` seul ne porte PAS le créatif, donc
        dupliquer sans passer par le miroir de créatif est impossible).
        ``adset_extra_fields`` porte la copie du budget/ciblage de la source
        (construit par l'appelant depuis le miroir — « adset = copie du payload
        miroir »). Renvoie ``{adset, ad}`` (les deux payloads Graph)."""
        adset = self.create_adset(
            name=new_adset_name, campaign_id=campaign_id,
            extra_fields=adset_extra_fields)
        new_adset_id = str((adset or {}).get('id') or '')
        if not new_adset_id:
            raise MetaError(
                "Duplication : création de l'ad set échouée (aucun id renvoyé).")
        extra = dict(ad_extra_fields or {})
        extra.pop('status', None)
        extra['creative'] = json.dumps({'creative_id': creative_id})
        ad = self.create_ad(
            name=new_ad_name, adset_id=new_adset_id, extra_fields=extra)
        return {'adset': adset, 'ad': ad}

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

    # ── ADSDEEP34 — A/B test NATIF Meta (ad_studies, SPLIT_TEST_V2) ──────────
    # Bornes documentées (dossier §7) : 2-5 cellules, ``treatment_percentage``
    # >= 10 %, somme des cellules = 100 %. Validées ICI (fail-fast) — jamais un
    # rejet Graph tardif après un aller-retour réseau.
    AD_STUDY_MIN_CELLS = 2
    AD_STUDY_MAX_CELLS = 5
    AD_STUDY_MIN_TREATMENT_PCT = 10

    @classmethod
    def _validate_ad_study_cells(cls, cells):
        cells = list(cells or [])
        if not (cls.AD_STUDY_MIN_CELLS <= len(cells) <= cls.AD_STUDY_MAX_CELLS):
            raise MetaError(
                "Une étude SPLIT_TEST_V2 exige entre "
                f"{cls.AD_STUDY_MIN_CELLS} et {cls.AD_STUDY_MAX_CELLS} cellules "
                f"(reçu {len(cells)}).")
        total_pct = sum(float(c.get('treatment_percentage', 0) or 0) for c in cells)
        if abs(total_pct - 100) > 0.01:
            raise MetaError(
                "La somme des treatment_percentage doit faire 100 "
                f"(reçu {total_pct}).")
        for cell in cells:
            pct = float(cell.get('treatment_percentage', 0) or 0)
            if pct < cls.AD_STUDY_MIN_TREATMENT_PCT:
                raise MetaError(
                    "Chaque cellule doit avoir treatment_percentage >= "
                    f"{cls.AD_STUDY_MIN_TREATMENT_PCT} % (reçu {pct} pour "
                    f"« {cell.get('name', '?')} »).")
        return cells

    def create_ad_study(self, *, name, cells, extra_fields=None):
        """ADSDEEP34 — Crée une étude A/B NATIVE Meta (``POST /act_<id>/ad_studies``,
        ``type=SPLIT_TEST_V2`` — dossier §7).

        ``cells`` : 2-5 dicts ``{name, treatment_percentage, campaigns|adsets|
        ads: [ids]}`` — ces ids référencent des objets DÉJÀ créés (par le reste
        du moteur, donc TOUJOURS nés PAUSED — cette méthode ne crée ni campagne
        ni adset elle-même et n'envoie AUCUN ``status`` : une étude ne porte pas
        de statut de type campagne/adset).

        IMMUABLE APRÈS LANCEMENT (dossier §7) : ``treatment_percentage`` et
        ``start_time`` ne peuvent plus changer une fois l'étude créée — l'UI
        DOIT l'annoncer à l'approbateur AVANT la proposition (``services.
        propose_ad_study`` porte l'avertissement) ; ce client, lui, ne fait que
        transmettre — il ne « réédite » jamais une étude déjà lancée."""
        cells = self._validate_ad_study_cells(cells)
        base = {'name': name, 'type': 'SPLIT_TEST_V2', 'cells': json.dumps(cells)}
        payload = dict(base)
        extras = dict(extra_fields or {})
        extras.pop('status', None)  # une étude ne porte pas de champ status
        payload.update(extras)
        return self._request(
            'POST', self._account_edge('ad_studies'), data=payload)

    def get_ad_study_results(self, study_id):
        """ADSDEEP34 — Lit (LECTURE SEULE) les résultats d'une étude native déjà
        créée (``GET /<study_id>``). Renvoie le dict brut (ou ``{}``) — la
        normalisation en ``DecisionLog`` vit dans ``services.
        sync_ad_study_results`` (aucun write Meta ici)."""
        payload = self._request('GET', f'{study_id}', params={'fields': (
            'id,name,type,cells,start_time,end_time,confidence_level,results')})
        return payload if isinstance(payload, dict) else {}

    # ── Éditions d'objets existants (ADSDEEP30 — JAMAIS de status) ───────────
    @staticmethod
    def _edit_payload(base, extra_fields):
        """Fusionne ``base`` + ``extra_fields`` en RETIRANT tout ``status``.

        Les méthodes d'édition (échange de créatif / renommage / plafond) ne
        touchent JAMAIS au statut : un ``status`` glissé via ``extra_fields`` est
        retiré et n'est jamais réémis — aucune d'elles ne peut donc activer /
        dé-pauser un objet (invariant permanent règle #3). À la DIFFÉRENCE des
        créations, on n'écrit PAS ``PAUSED`` : une édition laisse le statut Meta
        inchangé (elle ne repause pas non plus un objet en ligne — elle n'écrit
        aucun statut du tout)."""
        payload = dict(base)
        extras = dict(extra_fields or {})
        extras.pop('status', None)
        payload.update(extras)
        payload.pop('status', None)  # mot final : jamais de status sur une édition
        return payload

    def swap_ad_creative(self, *, ad_id, creative_spec=None, creative_id=None,
                         extra_fields=None):
        """ADSDEEP30 — Remplace le créatif d'une ad EXISTANTE (dossier §4).

        ``AdCreative`` est **write-once** pour son contenu : on ne peut pas éditer
        le texte / média d'un créatif en place. Le SEUL chemin est donc :

          1. créer un NOUVEAU adcreative (``POST /act_<id>/adcreatives``) portant
             le nouveau contenu (``creative_spec``) — sauf si ``creative_id`` est
             déjà fourni (réutilisation d'un créatif existant) ;
          2. le rattacher à l'ad SANS rien toucher d'autre :
             ``POST /<ad_id>`` avec ``{"creative": {"creative_id": <nouveau>}}``.

        Même ``ad_id`` → l'historique d'insights est conservé. AUCUN ``status``
        n'est envoyé à AUCUNE des deux étapes : la méthode ne peut ni créer un
        objet actif ni dé-pauser l'ad (invariant permanent règle #3). ⚠ côté Meta
        c'est un *significant edit* (re-review + reset d'apprentissage) et un
        changement de texte crée un NOUVEAU post (perte de preuve sociale) —
        l'avertissement est porté par la couche EngineAction (ADSDEEP31), pas ici.

        Renvoie ``{creative_id, created_creative, ad_update}``.
        """
        new_creative_id = str(creative_id or '').strip()
        created = None
        if not new_creative_id:
            if not creative_spec:
                raise MetaError(
                    "swap_ad_creative exige creative_spec ou creative_id.")
            # Les objets imbriqués (object_story_spec, asset_feed_spec…) voyagent
            # en JSON dans les paramètres de formulaire Meta. ``status`` retiré :
            # jamais posé sur le nouveau créatif non plus.
            spec = {}
            for key, value in dict(creative_spec).items():
                if key == 'status':
                    continue
                spec[key] = (json.dumps(value)
                             if isinstance(value, (dict, list)) else value)
            created = self._request(
                'POST', self._account_edge('adcreatives'), data=spec)
            new_creative_id = str((created or {}).get('id') or '').strip()
            if not new_creative_id:
                raise MetaError(
                    "Création du nouveau créatif échouée : aucun id renvoyé.")
        base = {'creative': json.dumps({'creative_id': new_creative_id})}
        payload = self._edit_payload(base, extra_fields)
        result = self._request('POST', f'{ad_id}', data=payload)
        return {
            'creative_id': new_creative_id,
            'created_creative': created,
            'ad_update': result if isinstance(result, dict) else {
                'result': result},
        }

    def rename_object(self, *, object_id, name, extra_fields=None):
        """ADSDEEP30 — Renomme un objet Meta (campagne / adset / ad / créatif) :
        le SEUL champ édité est ``name``. ``POST /<object_id>`` avec ``{name}``.
        Aucun ``status`` n'est jamais envoyé (invariant permanent : le renommage
        ne peut ni activer ni dé-pauser — règle #3)."""
        base = {'name': name}
        payload = self._edit_payload(base, extra_fields)
        return self._request('POST', f'{object_id}', data=payload)

    def set_adset_schedule(self, *, adset_id, adset_schedule, extra_fields=None):
        """ADSDEEP36 — Dayparting NATIF Meta : pose ``adset_schedule`` sur un ad
        set (exige côté Meta un ad set en BUDGET LIFETIME + pacing day_parting —
        contrainte NON vérifiable depuis ce seul appel réseau ; l'appelant
        (``services.propose_native_schedule``) choisit ce chemin uniquement pour
        les ad sets lifetime-budget, jamais pour du budget quotidien).

        Chaque plage DOIT être bornée à l'HEURE PLEINE (``start_minute``/
        ``end_minute`` multiples de 60) — validé ICI (fail-fast), jamais laissé
        remonter en erreur Graph tardive. Édition : AUCUN ``status`` n'est
        jamais envoyé (invariant permanent règle #3 — un horaire ne peut ni
        activer ni dé-pauser)."""
        for block in adset_schedule or []:
            start = block.get('start_minute')
            end = block.get('end_minute')
            if start is None or end is None or start % 60 != 0 or end % 60 != 0:
                raise MetaError(
                    "adset_schedule : chaque plage doit être bornée à l'heure "
                    f"pleine (minutes multiples de 60) — reçu start={start}, "
                    f"end={end}.")
        base = {'adset_schedule': json.dumps(list(adset_schedule or []))}
        payload = self._edit_payload(base, extra_fields)
        return self._request('POST', f'{adset_id}', data=payload)

    def set_campaign_spend_cap(self, *, campaign_id, spend_cap,
                               extra_fields=None):
        """ADSDEEP30 — Pose le plafond de dépense TOTAL d'une campagne
        (``spend_cap``, unités mineures Meta ; ``0`` = sans plafond — dossier §1).
        ``POST /<campaign_id>``. Un plafond ne PEUT QUE limiter la dépense — il
        n'active jamais rien : aucun ``status`` n'est envoyé (invariant permanent
        règle #3)."""
        base = {'spend_cap': spend_cap}
        payload = self._edit_payload(base, extra_fields)
        return self._request('POST', f'{campaign_id}', data=payload)

    # ── ADSDEEP50 — Éditer le texte d'un post de Page (message SEUL) ──────────
    def edit_page_post(self, *, post_id, message, extra_fields=None):
        """ADSDEEP50 — Édite le TEXTE d'un post de Page (``POST /<post_id>``).

        SEUL le ``message`` est éditable : le visuel (image/vidéo) d'un post
        PUBLIÉ est IMMUABLE côté Meta (dossier organic-posts §1 — le changer =
        supprimer + recréer, perte de l'historique d'engagement). Comme toute
        édition, AUCUN ``status`` n'est jamais envoyé (invariant permanent
        règle #3). La contrainte « posts créés par l'app SEULEMENT » est vérifiée
        en amont (``services.propose_edit_post`` refuse proprement un post non
        créé par l'app) — Meta la rejetterait de toute façon."""
        base = {'message': message}
        payload = self._edit_payload(base, extra_fields)
        return self._request('POST', f'{post_id}', data=payload)

    # ── ADSDEEP51 — Publier des posts de Page (organique, pages_manage_posts) ─
    # Fenêtre de programmation Meta (dossier organic-posts §2) : 10 min à 30 j.
    SCHEDULE_MIN_SECONDS = 10 * 60
    SCHEDULE_MAX_SECONDS = 30 * 24 * 3600
    # Taille max d'une vidéo (Resumable Upload API, dossier §2) : 1,75 Go.
    MAX_VIDEO_BYTES = int(1.75 * 1024 * 1024 * 1024)

    def _validate_schedule(self, scheduled_publish_time):
        """Fail-fast : une programmation doit tomber entre 10 min et 30 j dans le
        futur (jamais un rejet Graph tardif après un aller-retour réseau)."""
        try:
            ts = int(scheduled_publish_time)
        except (TypeError, ValueError):
            raise MetaError(
                "scheduled_publish_time doit être un horodatage unix (secondes).")
        delta = ts - int(time.time())
        if not (self.SCHEDULE_MIN_SECONDS <= delta <= self.SCHEDULE_MAX_SECONDS):
            raise MetaError(
                "La programmation d'un post doit tomber entre 10 minutes et "
                "30 jours dans le futur (dossier organic-posts §2).")

    def create_page_post(self, *, message='', link='', published=True,
                         scheduled_publish_time=None, attached_media=None,
                         extra_fields=None):
        """ADSDEEP51 — Crée un post via ``POST /<page_id>/feed``. Trois modes :

          * PUBLIÉ — ``published=True`` (affiché tout de suite) ;
          * DARK — ``published=False`` SANS programmation : objet post complet
            jamais affiché sur la Page, réutilisable en ad (``object_story_id``) ;
          * PROGRAMMÉ — ``published=False`` + ``scheduled_publish_time`` (fenêtre
            10 min-30 j revalidée ici, fail-fast).

        ``attached_media`` porte les ``{"media_fbid": …}`` des photos
        pré-uploadées (post multi-photos). Ce n'est PAS un objet publicitaire :
        aucun ``status`` de campagne/adset/ad n'est en jeu ici."""
        if scheduled_publish_time is not None:
            published = False
            self._validate_schedule(scheduled_publish_time)
        body = {'published': 'true' if published else 'false'}
        if message:
            body['message'] = message
        if link:
            body['link'] = link
        if scheduled_publish_time is not None:
            body['scheduled_publish_time'] = int(scheduled_publish_time)
        for i, media in enumerate(attached_media or []):
            body[f'attached_media[{i}]'] = json.dumps(media)
        body.update(dict(extra_fields or {}))
        return self._request('POST', self._page_edge('feed'), data=body)

    def upload_page_photo(self, *, image_url='', published=False, caption='',
                          extra_fields=None):
        """ADSDEEP51 — Upload une photo (``POST /<page_id>/photos``).
        ``published=False`` (défaut) sert au post multi-photos (récupérer le
        ``id``/media_fbid sans afficher) ; ``published=True`` = simple
        publication photo."""
        body = {'published': 'true' if published else 'false'}
        if image_url:
            body['url'] = image_url
        if caption:
            body['caption'] = caption
        body.update(dict(extra_fields or {}))
        return self._request('POST', self._page_edge('photos'), data=body)

    def create_multi_photo_post(self, *, message='', image_urls=None,
                                extra_fields=None):
        """ADSDEEP51 — Post multi-photos : upload chaque photo ``published=false``
        (récupère les media_fbid) puis ``POST /feed`` avec ``attached_media``
        (dossier organic-posts §2)."""
        media = []
        for url in image_urls or []:
            photo = self.upload_page_photo(image_url=url, published=False)
            fbid = str((photo or {}).get('id') or '').strip()
            if not fbid:
                raise MetaError(
                    "Upload photo échoué (aucun id/media_fbid renvoyé).")
            media.append({'media_fbid': fbid})
        return self.create_page_post(
            message=message, published=True, attached_media=media,
            extra_fields=extra_fields)

    def upload_page_video(self, *, file_url='', message='', file_size=None,
                          extra_fields=None):
        """ADSDEEP51 — Publie une vidéo (``POST /<page_id>/videos``). Les gros
        fichiers passent par la Resumable Upload API côté client d'upload ; ici on
        BORNE la taille à 1,75 Go (dossier §2, fail-fast) et on transmet
        ``file_url`` + ``description``."""
        if file_size is not None:
            try:
                size = int(file_size)
            except (TypeError, ValueError):
                size = 0
            if size > self.MAX_VIDEO_BYTES:
                raise MetaError(
                    "Vidéo trop lourde : 1,75 Go maximum (dossier "
                    "organic-posts §2).")
        body = {}
        if file_url:
            body['file_url'] = file_url
        if message:
            body['description'] = message
        body.update(dict(extra_fields or {}))
        return self._request('POST', self._page_edge('videos'), data=body)

    # ── ADSDEEP52 — Booster un post existant (object_story_id — preuve sociale) ─
    def boost_page_post(self, *, post_id, adset_id, name, extra_fields=None):
        """ADSDEEP52 — Booste un post EXISTANT : crée un adcreative portant
        ``object_story_id`` (la preuve sociale — J'aime/commentaires/partages —
        est PRÉSERVÉE ; on n'utilise JAMAIS ``object_story_spec`` ici, qui
        créerait un post NEUF aux compteurs à zéro) puis une ad qui le porte,
        née PAUSED (invariant permanent règle #3 — ``create_ad`` force PAUSED,
        aucune activation possible).

        Renvoie ``{creative, ad}`` (les deux payloads Graph)."""
        if not post_id:
            raise MetaError("boost_page_post exige un post_id.")
        creative = self._request(
            'POST', self._account_edge('adcreatives'),
            data={'object_story_id': post_id})
        creative_id = str((creative or {}).get('id') or '').strip()
        if not creative_id:
            raise MetaError(
                "Boost : création du créatif échouée (aucun id renvoyé).")
        extra = dict(extra_fields or {})
        extra.pop('status', None)
        extra['creative'] = json.dumps({'creative_id': creative_id})
        ad = self.create_ad(name=name, adset_id=adset_id, extra_fields=extra)
        return {'creative': creative, 'ad': ad}

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

    # ── ADSDEEP33 — Lot (batch) Graph : opérations SIMPLES groupées ──────────
    # ``POST /?batch=[...]`` (dossier write-surface §8) : 50 opérations MAX, PAS
    # transactionnel (chaque sous-réponse s'inspecte individuellement),
    # ``error_user_msg`` FAIT pour être montré verbatim à l'approbateur. AUCUNE
    # clé d'idempotence côté Graph — un retry réseau peut dupliquer ; c'est donc
    # le JOURNAL EngineAction (réclamation CAS avant tout appel réseau, cf.
    # ``services.apply_batch``) qui sert d'unique dédup, jamais ce client.
    MAX_BATCH_OPERATIONS = 50

    @staticmethod
    def _encode_batch_body(body):
        """Encode un dict de champs en corps ``application/x-www-form-urlencoded``
        (les objets imbriqués voyagent en JSON, comme sur tout appel Graph)."""
        from urllib.parse import quote_plus
        parts = []
        for key, value in dict(body or {}).items():
            raw = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            parts.append(f'{quote_plus(str(key))}={quote_plus(raw)}')
        return '&'.join(parts)

    def build_batch_op_rename(self, *, object_id, name):
        """ADSDEEP33 — Opération de lot : renommage (même garde que
        ``rename_object`` — AUCUN ``status`` ne peut y être glissé)."""
        payload = self._edit_payload({'name': name}, None)
        return {'method': 'POST', 'relative_url': object_id,
                'body': self._encode_batch_body(payload)}

    def build_batch_op_spend_cap(self, *, campaign_id, spend_cap):
        """ADSDEEP33 — Opération de lot : plafond de dépense (même garde que
        ``set_campaign_spend_cap``)."""
        payload = self._edit_payload({'spend_cap': spend_cap}, None)
        return {'method': 'POST', 'relative_url': campaign_id,
                'body': self._encode_batch_body(payload)}

    def build_batch_op_pause(self, *, object_id):
        """ADSDEEP33 — Opération de lot : mise en pause. Le corps FORCE
        ``status=PAUSED`` via ``_forced_status_payload`` (MÊME défense en
        profondeur que ``update_status_paused`` — invariant permanent règle #3 :
        aucune opération de lot ne peut jamais activer / dé-pauser quoi que ce
        soit)."""
        payload = self._forced_status_payload({}, None)
        return {'method': 'POST', 'relative_url': object_id,
                'body': self._encode_batch_body(payload)}

    def batch_execute(self, operations):
        """ADSDEEP33 — Exécute un LOT d'opérations Graph en UN SEUL appel HTTP.

        ``operations`` : liste de dicts ``{method, relative_url, body}`` (voir
        les ``build_batch_op_*`` ci-dessus). Renvoie la liste des résultats DANS
        LE MÊME ORDRE, chacun ``{'success': True, 'body': {...}}`` ou
        ``{'success': False, 'error': {...}, 'error_user_msg': '...'}`` —
        ``error_user_msg`` est repris VERBATIM du champ Graph fait pour être
        montré à l'approbateur (dossier §8). PAS TRANSACTIONNEL : une opération
        en erreur n'annule jamais les autres — chaque sous-réponse est inspectée
        indépendamment. Lève ``MetaError`` en amont si le lot dépasse
        ``MAX_BATCH_OPERATIONS`` (jamais un rejet Graph tardif)."""
        if not operations:
            return []
        if len(operations) > self.MAX_BATCH_OPERATIONS:
            raise MetaError(
                f"Lot Graph limité à {self.MAX_BATCH_OPERATIONS} opérations "
                f"(reçu {len(operations)}).")
        batch_spec = [
            {'method': op.get('method', 'POST'),
             'relative_url': op.get('relative_url', ''),
             **({'body': op['body']} if op.get('body') else {})}
            for op in operations
        ]
        raw = self._request('POST', '', data={'batch': json.dumps(batch_spec)})
        rows = raw if isinstance(raw, list) else []
        results = []
        for row in rows:
            row = row or {}
            code = row.get('code')
            body_raw = row.get('body')
            try:
                body = json.loads(body_raw) if isinstance(body_raw, str) else (body_raw or {})
            except (ValueError, TypeError):
                body = {}
            if not isinstance(body, dict):
                body = {}
            if code is not None and 200 <= int(code) < 300:
                results.append({'success': True, 'body': body})
            else:
                err = body.get('error') or {}
                results.append({
                    'success': False,
                    'error': err,
                    'error_user_msg': err.get('error_user_msg', '') or '',
                })
        # Graph peut renvoyer MOINS de lignes qu'attendu sur une panne partielle
        # (défense) : les opérations sans sous-réponse sont marquées en échec
        # explicite (jamais un succès silencieux non prouvé).
        while len(results) < len(operations):
            results.append({
                'success': False, 'error': {},
                'error_user_msg': 'Aucune sous-réponse Graph reçue pour cette opération.',
            })
        return results

    # ── Hygiène ──────────────────────────────────────────────────────────────
    def close(self):
        if self._owns_client:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
