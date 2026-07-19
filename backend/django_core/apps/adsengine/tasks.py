"""ENG6 — Beat Celery : synchro quotidienne des insights publicitaires.

Pour chaque société ayant une ``MetaConnection`` ACTIVE avec token, synchronise
les miroirs (campagnes/adsets/ads) puis upserte un ``InsightSnapshot`` par
campagne. **NO-OP propre** sans connexion active/token : la société est sautée,
aucun appel réseau n'est tenté (key-gated, comme le reste du moteur).

Idempotent : la synchro repose sur ``sync.py`` (upsert par ``meta_id`` / clé
d'insight datée), donc deux exécutions sur les mêmes données Meta laissent le
même état. Best-effort par société — une exception sur une société n'empêche
jamais les suivantes.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``) ; planifié
dans ``erp_agentique/celery.py`` (queue ``scheduled``, voir
``CELERY_TASK_ROUTES``).
"""
import datetime
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


# ADSDEEP2 — champs insights niveau ad/adset (dossier insights-api §1 + §3).
# Une seule liste de champs demandée à l'edge COMPTE avec ``level=ad|adset`` :
# diffusion + conversion (``actions[]``) + métriques vidéo (AdsActionStats).
AD_INSIGHT_FIELDS = (
    'spend', 'impressions', 'reach', 'clicks', 'frequency',
    'inline_link_clicks', 'results', 'actions',
    # PUB32 — diagnostics de classement Meta (niveau ad uniquement) : proxys
    # NÉGATIFS lus par le garde-fou dur quality_ranking_guard, jamais une
    # récompense. NB : « opportunity score » (Ads Manager) n'est PAS exposé par
    # l'API Insights — c'est une recommandation UI niveau compte (edge
    # ``recommendations``), non une métrique par ad → non synchronisé ici.
    'quality_ranking', 'engagement_rate_ranking', 'conversion_rate_ranking',
    'video_p25_watched_actions', 'video_p50_watched_actions',
    'video_p75_watched_actions', 'video_p95_watched_actions',
    'video_p100_watched_actions', 'video_play_actions',
    'video_6_sec_watched_actions', 'video_15_sec_watched_actions',
    'video_30_sec_watched_actions', 'video_thruplay_watched_actions',
    'video_avg_time_watched_actions',
)


def _clean_ranking(value):
    """PUB32 — Normalise un diagnostic de classement Meta (ordinal). Renvoie la
    chaîne bornée (ex. ``below_average``/``UNKNOWN``), ou ``None`` si absente —
    ``None`` ne réécrit jamais un classement déjà connu (protection re-sync)."""
    if value in (None, ''):
        return None
    return str(value).strip()[:16] or None


# Fenêtre glissante (jours) pour la synchro ad/adset — les insights fins sont
# lus sur les 7 derniers jours (le détail campagne reste sur ``maximum``).
AD_INSIGHT_WINDOW_DAYS = 7


def _account_node(conn):
    """Nœud de compte publicitaire (``act_<id>``) depuis la connexion, ou ''."""
    acct = str(conn.ad_account_id or '').strip()
    if not acct:
        return ''
    return acct if acct.startswith('act_') else f'act_{acct}'


def _handle_meta_auth_error(conn, exc):
    """PUB20 — Un ``MetaAuthError`` (token 190) ne doit JAMAIS être avalé en
    silence : la synchro marque la connexion (état + bandeau) et émet une
    ``EngineAlert`` ``token_invalide`` CRITIQUE. Dédup best-effort par connexion
    (une alerte non acquittée déjà présente → pas de réémission à chaque beat).

    Best-effort : ni le marquage ni l'alerte ne relèvent l'exception — la société
    est neutralisée, les suivantes continuent. Renvoie l'alerte créée ou ``None``.
    """
    from .guardrails import ALERT_TOKEN_INVALID
    from .models import EngineAlert

    company = conn.company
    logger.warning(
        'adsengine ALERTE [token_invalide] société=%s connexion=%s: %s',
        getattr(company, 'pk', None), conn.pk, exc)
    try:
        conn.mark_token_invalid()
    except Exception:  # noqa: BLE001 — l'état ne doit pas empêcher l'alerte
        logger.warning(
            'adsengine: échec marquage token invalide société %s',
            getattr(company, 'pk', None), exc_info=True)
    entity_key = f'connection:{conn.pk}'
    message = (
        "Connexion Meta rompue : le token d'accès est expiré ou invalide "
        "(code 190). La synchronisation publicitaire est à l'arrêt jusqu'au "
        "renouvellement du token dans « Connexion ».")
    try:
        already = EngineAlert.objects.filter(
            company=company, alert_type=ALERT_TOKEN_INVALID,
            entity_key=entity_key, acknowledged=False).exists()
        if already:
            return None
        return EngineAlert.objects.create(
            company=company, alert_type=ALERT_TOKEN_INVALID, message=message,
            severity=EngineAlert.Severity.CRITIQUE, entity_key=entity_key,
            detail={'code': getattr(exc, 'code', None),
                    'subcode': getattr(exc, 'subcode', None)})
    except Exception:  # pragma: no cover - défensif, l'alerte est déjà loggée
        logger.warning(
            'adsengine: échec persistance alerte token_invalide société %s',
            getattr(company, 'pk', None), exc_info=True)
        return None


# ── ADSDEEP32 — Phase d'apprentissage par ad set (learning_stage_info) ────────
# Champs demandés à l'edge ``adsets`` pour miroiter la phase d'apprentissage.
ADSET_LEARNING_FIELDS = ('id', 'learning_stage_info')


def _parse_meta_ts(value):
    """Horodatage Meta (unix int/str OU ISO-8601) → datetime aware, ou None."""
    if value in (None, ''):
        return None
    from django.utils import timezone as _tz
    try:
        # Unix (secondes) → datetime aware UTC directement (jamais via une
        # heure locale naïve, qui décalerait l'instant selon le fuseau serveur).
        return datetime.datetime.fromtimestamp(
            int(value), datetime.timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        pass
    try:
        dt = datetime.datetime.fromisoformat(
            str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None
    if _tz.is_naive(dt):
        dt = _tz.make_aware(dt, datetime.timezone.utc)
    return dt


def sync_adset_learning(company, client):
    """ADSDEEP32 — Miroite ``learning_stage_info`` par ad set (dossier §2).

    Lit ``GET /act_<id>/adsets?fields=learning_stage_info`` et met à jour chaque
    ``AdSetMirror`` : ``learning_status`` (LEARNING/SUCCESS/FAIL normalisé, '' si
    inconnu), ``last_sig_edit`` (last_sig_edit_ts) et le dict brut
    ``learning_stage_info``. Best-effort ; NO-OP propre si le client n'expose pas
    ``get_adsets``. Renvoie le nombre d'ad sets mis à jour."""
    from .models import AdSetMirror

    reader = getattr(client, 'get_adsets', None)
    if not callable(reader):
        return 0
    try:
        rows = reader(fields=ADSET_LEARNING_FIELDS)
    except Exception:  # noqa: BLE001 — l'apprentissage n'empêche jamais la synchro
        return 0
    by_id = {
        str(r.get('id') or '').strip(): r
        for r in (rows or []) if isinstance(r, dict)}
    updated = 0
    for adset in AdSetMirror.objects.filter(company=company):
        row = by_id.get(adset.meta_id)
        if not row:
            continue
        info = row.get('learning_stage_info')
        if not isinstance(info, dict):
            info = {}
        status = str(info.get('status') or '').strip().upper()
        if status not in ('LEARNING', 'SUCCESS', 'FAIL'):
            status = ''
        last_sig = _parse_meta_ts(info.get('last_sig_edit_ts'))
        adset.learning_stage_info = info
        adset.learning_status = status
        if last_sig is not None:
            adset.last_sig_edit = last_sig
        adset.save()
        updated += 1
    return updated


def _sync_level_insights(company, conn, client, *, level,
                         incremental_available=False):
    """ADSDEEP2 — Synchronise les snapshots niveau ``ad`` ou ``adset``.

    Tire les insights de l'edge COMPTE avec ``level=ad|adset``,
    ``time_increment=1`` (une ligne par jour) sur une fenêtre 7 j glissants,
    puis upserte un ``InsightSnapshot`` par (miroir, jour) — colonnes typées
    ADSDEEP1 comprises. Les rows sans id d'objet, ou sans miroir correspondant,
    sont ignorés (jamais d'erreur). Débloque ``attribution.variant_attribution``,
    la fréquence dans ``rules_engine`` et le CBO de ``budget_applier`` — tous
    DÉJÀ codés et affamés de snapshots ad/adset (dossier existing-map §1)."""
    from . import sync
    from .models import AdMirror, AdSetMirror
    from .platforms.base import normalize_insight_row

    node = _account_node(conn)
    if not node:
        return
    is_ad = level == 'ad'
    id_field = 'ad_id' if is_ad else 'adset_id'
    mirror_model = AdMirror if is_ad else AdSetMirror
    today = datetime.date.today()
    since = today - datetime.timedelta(days=AD_INSIGHT_WINDOW_DAYS - 1)
    # PUB35 — n'ajoute les champs incrémentaux QUE si le compte les expose (probe
    # validé en amont) et seulement au niveau ad — sinon un champ inconnu ferait
    # échouer tout le pull (dégradation propre : on ne les demande pas).
    fields = AD_INSIGHT_FIELDS + (id_field,)
    if is_ad and incremental_available:
        from .meta_client import INCREMENTAL_ATTRIBUTION_FIELDS
        fields = fields + INCREMENTAL_ATTRIBUTION_FIELDS
    rows = client.get_insights(
        node,
        fields=fields,
        params={
            'level': level,
            'time_increment': 1,
            'time_range': {
                'since': since.isoformat(), 'until': today.isoformat()},
        })
    mirrors = {
        m.meta_id: m
        for m in mirror_model.objects.filter(company=company)}
    for row in rows or []:
        obj_id = str(row.get(id_field) or '').strip()
        mirror = mirrors.get(obj_id)
        if mirror is None:
            continue  # ad/adset non miroité (synchro miroirs à faire d'abord)
        day = _parse_date(row.get('date_start')) or today
        norm = normalize_insight_row(row)
        # PUB32 — classements Meta seulement au niveau ad (l'adset ne les expose
        # pas ; passer None les laisse intacts sur l'adset).
        # PUB35 — attribution incrémentale (si disponible) parsée par ad.
        ranking_kwargs = {}
        incremental = None
        if is_ad:
            ranking_kwargs = {
                'quality_ranking': _clean_ranking(row.get('quality_ranking')),
                'engagement_rate_ranking': _clean_ranking(
                    row.get('engagement_rate_ranking')),
                'conversion_rate_ranking': _clean_ranking(
                    row.get('conversion_rate_ranking')),
            }
            if incremental_available:
                from .meta_client import parse_incremental_attribution
                incremental = parse_incremental_attribution(row) or None
        sync.upsert_insight(
            company, mirror, date=day,
            spend=norm['spend'], results=norm['results'],
            frequency=norm['frequency'], cpl=norm['cpl'],
            impressions=norm['impressions'], reach=norm['reach'],
            clicks=norm['clicks'], link_clicks=norm['link_clicks'],
            conversations=norm['conversations'],
            leads_count=norm['leads_count'],
            video_metrics=norm['video_metrics'],
            incremental_attribution=incremental, **ranking_kwargs)


def _sync_company(conn):
    """Synchronise UNE société depuis sa connexion Meta active (avec token).

    Importe les miroirs puis un instantané d'insight par campagne. Le client
    Meta est importé LOCALEMENT (patchable via ``apps.adsengine.meta_client``).
    """
    from . import sync
    from .meta_client import MetaClient
    from .models import AdCampaignMirror

    company = conn.company
    client = MetaClient.from_connection(conn)

    # Devise du compte (USD, MAD…) — Meta rapporte TOUS les montants dans la
    # devise du COMPTE publicitaire : on la mémorise pour étiqueter correctement
    # les chiffres côté ERP. Best-effort, jamais bloquant pour la synchro.
    try:
        currency = (client.get_account(fields=('currency',))
                    or {}).get('currency') or ''
        if currency and currency != conn.currency:
            conn.currency = currency
            conn.save(update_fields=['currency'])
    except Exception:  # noqa: BLE001 — la devise n'empêche jamais la synchro
        pass

    sync.sync_campaigns(company, client.get_campaigns())
    sync.sync_adsets(company, client.get_adsets())
    sync.sync_ads(company, client.get_ads())

    # PUB35 — probe UNE fois : le compte expose-t-il l'attribution incrémentale ?
    # (déploiement progressif Meta — jamais supposé ; un champ inconnu casserait
    # tout le pull insights, d'où le probe préalable.) Best-effort.
    incremental_available = False
    try:
        incremental_available = client.incremental_attribution_available()
    except Exception:  # noqa: BLE001 — le probe ne bloque jamais la synchro
        incremental_available = False

    # ADSDEEP2 — snapshots niveau adset PUIS ad (edge compte, level=…). Placés
    # AVANT la boucle campagne pour que le dernier appel get_insights reste
    # celui de la campagne (fenêtre ``maximum`` — contrat ENG6 préservé).
    _sync_level_insights(company, conn, client, level='adset')
    _sync_level_insights(company, conn, client, level='ad',
                         incremental_available=incremental_available)

    # ADSDEEP32 — phase d'apprentissage par ad set (learning_stage_info).
    sync_adset_learning(company, client)

    # ADSDEEP11 — miroir du créatif LIVE de chaque ad (best-effort).
    sync_ad_creatives(company, client)

    # ADSDEEP49 — miroir des posts organiques de la Page (best-effort).
    sync_page_posts(company, conn, client)

    # ADSDEEP53 — miroir des commentaires (posts organiques + dark/ad posts).
    sync_comments_for_company(company, client)

    # ADSDEEP55 — miroir des médias Instagram + leurs commentaires (best-effort).
    sync_instagram_for_company(company, conn, client)

    today = datetime.date.today()
    for camp in AdCampaignMirror.objects.filter(company=company):
        # ENG6 — insights sur TOUT l'historique, ventilés par JOUR. Sans
        # ``date_preset``, l'API Graph ne renvoie qu'une fenêtre récente par
        # défaut -> dépense tronquée (ex. 90 MAD au lieu de >10 000) et donc un
        # coût-par-signature FAUX (~100x trop bas). ``maximum`` couvre la vie de
        # la campagne ; ``time_increment=1`` => une ligne (donc un snapshot) par
        # jour : somme EXACTE + upsert idempotent par date (aucun double comptage
        # entre deux synchros, chaque jour étant réécrit à sa vraie valeur).
        rows = client.get_insights(
            camp.meta_id,
            params={'date_preset': 'maximum', 'time_increment': 1})
        for row in rows:
            day = _parse_date(row.get('date_start')) or today
            sync.upsert_insight(
                company, camp, date=day,
                spend=row.get('spend'), results=row.get('results'),
                frequency=row.get('frequency'), cpl=row.get('cpl'))

    # PUB20 — la synchro a réussi de bout en bout : le token refonctionne, on
    # lève tout état « token mort » posé lors d'un cycle précédent (idempotent).
    conn.clear_token_invalid()


# ── ADSDEEP8 — Spécifications de breakdown (combos LÉGAUX uniquement) ─────────
# Dossier insights-api §2 : seules certaines permutations passent, et les
# breakdowns HORAIRES perdent reach/frequency/unique_*. Chaque spec porte les
# ``breakdowns`` Meta, la liste de ``fields`` sûre sous CE breakdown, et une
# fonction qui fabrique la ``key`` de ventilation stockée (ex. "25-34/f").
# Champs de base ventilables partout (jamais reach/frequency ici — ils sautent
# sous certains breakdowns ; on ne les demande qu'où c'est légal).
_BREAKDOWN_BASE_FIELDS = ('spend', 'impressions', 'clicks', 'actions')


def _key_age_gender(row):
    age = str(row.get('age') or '').strip()
    gender = str(row.get('gender') or '').strip()
    return f'{age}/{gender[:1]}' if age or gender else ''


def _key_platform(row):
    plat = str(row.get('publisher_platform') or '').strip()
    pos = str(row.get('platform_position') or '').strip()
    # "instagram/instagram_reels" → "instagram/reels" (le préfixe redondant sauté).
    pos = pos.replace(f'{plat}_', '') if plat and pos.startswith(plat) else pos
    return f'{plat}/{pos}' if plat or pos else ''


def _key_region(row):
    return str(row.get('region') or '').strip()


def _key_hourly(row):
    raw = str(
        row.get('hourly_stats_aggregated_by_advertiser_time_zone') or '').strip()
    # "14:00:00 - 14:59:59" → "14"
    return raw.split(':', 1)[0] if raw else ''


# dimension → {breakdowns, fields, key_fn}. Les fields d'HOURLY excluent
# volontairement reach/frequency (combo illégal — dossier §2).
BREAKDOWN_SPECS = {
    'age_gender': {
        'breakdowns': ('age', 'gender'),
        'fields': _BREAKDOWN_BASE_FIELDS,
        'key_fn': _key_age_gender,
    },
    'platform': {
        'breakdowns': ('publisher_platform', 'platform_position'),
        'fields': _BREAKDOWN_BASE_FIELDS,
        'key_fn': _key_platform,
    },
    'region': {
        'breakdowns': ('region',),
        'fields': _BREAKDOWN_BASE_FIELDS,
        'key_fn': _key_region,
    },
    'hourly': {
        'breakdowns': ('hourly_stats_aggregated_by_advertiser_time_zone',),
        # PAS de reach/frequency/unique_* sous breakdown horaire (illégal).
        'fields': _BREAKDOWN_BASE_FIELDS,
        'key_fn': _key_hourly,
    },
}

# Fenêtre glissante (jours) des breakdowns — agrégat sur 28 j (pas de
# time_increment : une ligne par clé de ventilation, pas par jour).
BREAKDOWN_WINDOW_DAYS = 28


def sync_breakdowns_for_campaign(company, client, campaign_mirror):
    """ADSDEEP8 — Synchronise les 4 dimensions de breakdown d'UNE campagne.

    Pour chaque dimension (âge×genre, placement, région, horaire) tire l'insight
    ventilé sur une fenêtre 28 j glissants avec les combos LÉGAUX uniquement
    (``BREAKDOWN_SPECS``) et upserte une ligne ``InsightBreakdown`` par clé.
    Idempotent (upsert par clé). Best-effort par dimension : une dimension en
    échec n'empêche pas les autres. Renvoie le nombre de lignes upsertées."""
    from .models import InsightBreakdown
    from .platforms.base import normalize_insight_row

    today = datetime.date.today()
    since = today - datetime.timedelta(days=BREAKDOWN_WINDOW_DAYS - 1)
    written = 0
    for dimension, spec in BREAKDOWN_SPECS.items():
        try:
            rows = client.get_insights(
                campaign_mirror.meta_id,
                fields=spec['fields'],
                params={
                    'breakdowns': ','.join(spec['breakdowns']),
                    'time_range': {
                        'since': since.isoformat(), 'until': today.isoformat()},
                })
        except Exception:  # noqa: BLE001 — une dimension en échec n'arrête pas
            continue
        for row in rows or []:
            key = spec['key_fn'](row)
            if not key:
                continue
            norm = normalize_insight_row(row)
            InsightBreakdown.upsert(
                company, campaign_mirror, date=today,
                dimension=dimension, key=key,
                spend=norm['spend'], impressions=norm['impressions'],
                clicks=norm['clicks'], results=norm['results'],
                conversations=norm['conversations'])
            written += 1
    return written


@shared_task(name='adsengine.sync_breakdowns_weekly')
def sync_breakdowns_weekly():
    """ADSDEEP8 — Beat HEBDO : synchronise les breakdowns de chaque campagne
    miroir des sociétés à connexion Meta active. NO-OP propre sans connexion
    live. Best-effort par société. Renvoie le nombre de campagnes traitées."""
    from authentication.selectors import active_companies

    from .meta_client import MetaAuthError, MetaClient
    from .models import AdCampaignMirror, MetaConnection

    processed = 0
    for company in active_companies():
        conn = MetaConnection.objects.filter(
            company=company, enabled=True).first()
        if conn is None or not conn.is_live:
            continue
        try:
            client = MetaClient.from_connection(conn)
            for camp in AdCampaignMirror.objects.filter(company=company):
                sync_breakdowns_for_campaign(company, client, camp)
                processed += 1
        except MetaAuthError as exc:
            _handle_meta_auth_error(conn, exc)  # PUB20 — jamais silencieux
            continue
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.sync_breakdowns_weekly: échec société %s',
                company.pk, exc_info=True)
            continue
    logger.info(
        'adsengine.sync_breakdowns_weekly: %s campagne(s) traitée(s)',
        processed)
    return {'campaigns_processed': processed}


def sync_ad_creatives(company, client):
    """ADSDEEP11 — Miroite le créatif LIVE de chaque ad d'une société.

    Lit ``GET /<ad>?fields=creative{…}`` par ad et upserte le miroir (idempotent,
    OneToOne). Best-effort par ad ; NO-OP propre si le client n'expose pas
    ``get_ad_creative`` (mock ancien). Renvoie le nombre de miroirs upsertés."""
    from . import sync
    from .models import AdMirror

    fetch = getattr(client, 'get_ad_creative', None)
    if not callable(fetch):
        return 0
    written = 0
    for ad in AdMirror.objects.filter(company=company):
        try:
            creative = fetch(ad.meta_id)
        except Exception:  # noqa: BLE001 — une ad en échec n'arrête pas les autres
            continue
        if creative:
            sync.sync_ad_creative(company, ad, creative)
            written += 1
    return written


def sync_page_posts(company, conn, client):
    """ADSDEEP49 — Miroite les posts ORGANIQUES de la Page (best-effort).

    Lit ``GET /<page>/posts`` puis croise ``GET /<page>/ads_posts`` pour marquer
    ``ad_linked``. ``created_by_app`` (posts éditables — l'app ne peut éditer que
    les siens) est déduit de l'``app_id`` lu dans les credentials write-only de la
    connexion. NO-OP propre si le client n'expose pas ``get_page_posts`` (mock
    ancien) ou si la connexion n'a pas de ``page_id``. Renvoie le nombre de
    miroirs upsertés."""
    from . import sync

    reader = getattr(client, 'get_page_posts', None)
    if not callable(reader) or not (conn.page_id or ''):
        return 0
    try:
        posts = reader()
    except Exception:  # noqa: BLE001 — les posts n'empêchent jamais la synchro
        return 0
    ad_ids = set()
    get_ads = getattr(client, 'get_ads_posts_ids', None)
    if callable(get_ads):
        try:
            ad_ids = get_ads()
        except Exception:  # noqa: BLE001 — cross-check best-effort
            ad_ids = set()
    app_id = str((conn.credentials or {}).get('app_id') or '')
    mirrors = sync.sync_page_posts(
        company, posts, ad_linked_ids=ad_ids, app_id=app_id)
    return len(mirrors)


def sync_comments_for_company(company, client):
    """ADSDEEP53 — Miroite les commentaires de TOUS les objets commentables d'une
    société : (a) chaque post organique miroir (``PagePostMirror``) ; (b) chaque
    dark/ad post via l'``effective_object_story_id`` du créatif miroir
    (``AdCreativeMirror``). Best-effort par objet ; NO-OP propre si le client
    n'expose pas ``get_object_comments`` (mock ancien). Renvoie le nombre de
    commentaires miroités."""
    from . import comments as comments_mod
    from .models import AdCreativeMirror, PagePostMirror

    reader = getattr(client, 'get_object_comments', None)
    if not callable(reader):
        return 0
    written = 0

    def _pull(object_meta_id, source):
        nonlocal written
        if not object_meta_id:
            return
        try:
            rows = reader(object_meta_id)
        except Exception:  # noqa: BLE001 — un objet en échec n'arrête pas les autres
            return
        mirrors = comments_mod.sync_comments(
            company, rows, object_meta_id=object_meta_id, source=source)
        written += len(mirrors)

    # (a) Posts organiques.
    for post in PagePostMirror.objects.filter(company=company):
        _pull(post.meta_id, 'post')

    # (b) Dark/ad posts : l'ID du post diffusé vit sur le créatif miroir.
    seen = set()
    for cm in (AdCreativeMirror.objects
               .filter(company=company)
               .exclude(effective_object_story_id='')):
        osid = str(cm.effective_object_story_id or '').strip()
        if osid and osid not in seen:
            seen.add(osid)
            _pull(osid, 'ad')

    return written


def sync_instagram_for_company(company, conn, client):
    """ADSDEEP55 — Miroite le compte Instagram Business relié : d'abord résout
    l'``ig_user_id`` (via ``GET /<page>?fields=instagram_business_account`` s'il
    manque, et le persiste sur la connexion), puis upserte les médias
    (``caption`` en LECTURE SEULE) et, par média, leurs commentaires. Best-effort ;
    NO-OP propre si le client n'expose pas ``get_ig_media`` (mock ancien) ou si
    aucun compte IG n'est relié. Renvoie le nombre de médias miroités."""
    from . import instagram as ig

    reader = getattr(client, 'get_ig_media', None)
    if not callable(reader):
        return 0

    # Résolution de l'ig_user_id (best-effort) si la connexion n'en a pas encore.
    if not getattr(client, 'ig_user_id', None):
        resolver = getattr(client, 'get_page_ig_account', None)
        if callable(resolver) and (conn.page_id or ''):
            try:
                ig_id = str(resolver() or '').strip()
            except Exception:  # noqa: BLE001 — la résolution IG n'arrête pas la synchro
                ig_id = ''
            if ig_id:
                client.ig_user_id = ig_id
                if getattr(conn, 'ig_user_id', '') != ig_id:
                    conn.ig_user_id = ig_id
                    conn.save(update_fields=['ig_user_id'])
    if not getattr(client, 'ig_user_id', None):
        return 0

    try:
        media_rows = reader()
    except Exception:  # noqa: BLE001 — les médias n'empêchent jamais la synchro
        return 0
    mirrors = ig.sync_ig_media(company, media_rows)

    get_comments = getattr(client, 'get_ig_media_comments', None)
    if callable(get_comments):
        for m in mirrors:
            try:
                rows = get_comments(m.meta_id)
            except Exception:  # noqa: BLE001 — un média en échec n'arrête pas les autres
                continue
            ig.sync_ig_comments(company, rows, media_meta_id=m.meta_id)
    return len(mirrors)


def pull_ad_leads_for_company(company, conn, client):
    """ADSDEEP18 — Pull-sync des leads lead-form d'une société.

    Pour chaque ad miroir, tire ``GET /<ad_id>/leads`` (fenêtre Meta 90 j),
    résout adset/campaign via l'ad, crée le lead CRM via le MÊME service que le
    webhook (``crm.services.create_lead_from_meta_lead_ads`` — idempotent par
    ``leadgen_id``, jamais un doublon) et émet ``meta_lead_captured`` pour que le
    MÊME récepteur upserte le MetaLeadMirror : webhook et pull CONVERGENT sur le
    même miroir. Best-effort par ad. Renvoie le nombre de leads traités."""
    from core.events import meta_lead_captured

    from .models import AdMirror

    get_leads = getattr(client, 'get_ad_leads', None)
    if not callable(get_leads):
        return 0
    processed = 0
    # Cache adset/campaign par ad (une seule résolution par ad).
    for ad in AdMirror.objects.filter(company=company):
        try:
            leads = get_leads(ad.meta_id)
        except Exception:  # noqa: BLE001 — une ad en échec n'arrête pas les autres
            continue
        if not leads:
            continue
        try:
            targeting = client.get_ad_targeting_ids(ad.meta_id)
        except Exception:  # noqa: BLE001
            targeting = {'adset_id': '', 'campaign_id': ''}
        for lead_row in leads:
            leadgen_id = str(lead_row.get('id') or '').strip()
            if not leadgen_id:
                continue
            field_data = lead_row.get('field_data') or []
            form_id = str(lead_row.get('form_id') or '')
            try:
                from apps.crm.services import create_lead_from_meta_lead_ads
                lead = create_lead_from_meta_lead_ads(
                    company=company, leadgen_id=leadgen_id,
                    field_data=field_data, ad_id=ad.meta_id,
                    adgroup_id=targeting.get('adset_id', ''), form_id=form_id)
            except Exception:  # noqa: BLE001 — un lead en échec n'arrête pas
                logger.warning(
                    'adsengine.pull_ad_leads: création lead échouée (%s)',
                    leadgen_id, exc_info=True)
                continue
            # Même événement que le webhook → même récepteur → même miroir.
            try:
                meta_lead_captured.send(
                    sender='adsengine.pull_ad_leads', lead=lead,
                    company=company, leadgen_id=leadgen_id, ad_id=ad.meta_id,
                    adset_id=targeting.get('adset_id', ''),
                    campaign_id=targeting.get('campaign_id', ''),
                    form_id=form_id, created_time=lead_row.get('created_time'),
                    is_organic=False)
            except Exception:  # noqa: BLE001 — best-effort
                pass
            processed += 1
    return processed


@shared_task(name='adsengine.pull_meta_leads')
def pull_meta_leads():
    """ADSDEEP18 — Beat : pull-sync des leads lead-form des sociétés à connexion
    Meta active. NO-OP propre sans connexion live. Best-effort par société."""
    from authentication.selectors import active_companies

    from .meta_client import MetaAuthError, MetaClient
    from .models import MetaConnection

    total = 0
    for company in active_companies():
        conn = MetaConnection.objects.filter(
            company=company, enabled=True).first()
        if conn is None or not conn.is_live:
            continue
        try:
            client = MetaClient.from_connection(conn)
            total += pull_ad_leads_for_company(company, conn, client)
        except MetaAuthError as exc:
            _handle_meta_auth_error(conn, exc)  # PUB20 — jamais silencieux
            continue
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.pull_meta_leads: échec société %s',
                company.pk, exc_info=True)
            continue
    logger.info('adsengine.pull_meta_leads: %s lead(s) traité(s)', total)
    return {'leads_processed': total}


@shared_task(name='adsengine.sync_insights_daily')
def sync_insights_daily():
    """ENG6 — Synchro quotidienne des insights, société par société.

    NO-OP propre tant qu'aucune ``MetaConnection`` n'est active + tokenisée
    (``is_live``) : la société est sautée sans aucun appel réseau. Best-effort
    par société ; renvoie le nombre de sociétés réellement synchronisées.
    """
    from authentication.selectors import active_companies

    from .meta_client import MetaAuthError
    from .models import MetaConnection

    synced = 0
    for company in active_companies():
        conn = MetaConnection.objects.filter(
            company=company, enabled=True).first()
        if conn is None or not conn.is_live:
            continue  # NO-OP : rien à faire sans connexion active + token
        try:
            _sync_company(conn)
            synced += 1
        except MetaAuthError as exc:
            # PUB20 — token mort : alerte + bandeau, jamais un swallow silencieux.
            _handle_meta_auth_error(conn, exc)
            continue
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.sync_insights_daily: échec société %s',
                company.pk, exc_info=True)
            continue

    logger.info(
        'adsengine.sync_insights_daily: %s société(s) synchronisée(s)', synced)
    return {'companies_synced': synced}


@shared_task(name='adsengine.generate_weekly_brief')
def generate_weekly_brief():
    """ENG11 — Génère le brief hebdomadaire déterministe de chaque société.

    Best-effort par société ; ne génère un brief que pour les sociétés ayant au
    moins un miroir de campagne (rien à résumer sinon). Idempotent : le brief est
    upserté par ``(company, period_start)``. Renvoie le nombre de briefs générés.
    """
    from authentication.selectors import active_companies

    from . import brief as brief_mod
    from .models import AdCampaignMirror

    generated = 0
    for company in active_companies():
        if not AdCampaignMirror.objects.filter(company=company).exists():
            continue  # rien à résumer tant qu'aucune campagne n'est synchronisée
        try:
            brief_mod.build_brief(company)
            generated += 1
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.generate_weekly_brief: échec société %s',
                company.pk, exc_info=True)
            continue

    logger.info(
        'adsengine.generate_weekly_brief: %s brief(s) généré(s)', generated)
    return {'briefs_generated': generated}


@shared_task(name='adsengine.daily_ads_digest')
def daily_ads_digest():
    """ADSDEEP62 — Digest quotidien FR (dépense/conversations/leads/
    signatures/alertes actives/top ad de la veille), émis via le moteur de
    notifications unifié, opt-out par utilisateur respecté. Voir
    ``digest.py`` pour la logique — best-effort par société, NO-OP propre
    sans campagne synchronisée (même garde que ``generate_weekly_brief``)."""
    from . import digest as digest_mod

    return digest_mod.run_daily_digest_for_all()


def _evaluate_ranking_guards_for_company(company):
    """PUB32 — Câble le garde-fou DUR ``signal_guards.quality_ranking_guard``
    (quadrant SIG2, BRAKE-ONLY) resté sans appelant production.

    Pour chaque ad dont le dernier snapshot porte un ``quality_ranking``
    « below_average » soutenu (≥500 impr., fenêtre Meta), émet une ``EngineAlert``
    de FREIN recommandant la pause à un humain. C'est un frein (∈
    ``BRAKE_ACTIONS``) : il ne propose JAMAIS d'accélération et ne CONTOURNE PAS
    le spine propose→approve (aucune pause n'est appliquée automatiquement — la
    décision reste humaine via la boîte d'approbation). Dédup par ad
    (``entity_key``). Renvoie le nombre d'alertes émises."""
    from django.contrib.contenttypes.models import ContentType

    from . import signal_guards
    from .guardrails import ALERT_GUARDRAIL
    from .models import AdMirror, EngineAlert, GuardrailConfig, InsightSnapshot

    config = GuardrailConfig.objects.filter(company=company).first()
    ct = ContentType.objects.get_for_model(AdMirror)
    emitted = 0
    for ad in AdMirror.objects.filter(company=company):
        snap = (InsightSnapshot.objects
                .filter(company=company, content_type=ct, object_id=ad.pk)
                .exclude(quality_ranking='')
                .order_by('-date').first())
        if snap is None:
            continue
        verdict = signal_guards.quality_ranking_guard(
            {'quality_ranking': snap.quality_ranking,
             'impressions': snap.impressions}, config)
        if not verdict.triggered:
            continue
        entity_key = f'ad:{ad.pk}'
        if EngineAlert.objects.filter(
                company=company, alert_type=ALERT_GUARDRAIL,
                entity_key=entity_key, acknowledged=False).exists():
            continue  # dédup : une alerte non acquittée existe déjà pour cette ad
        logger.warning(
            'adsengine ALERTE [quality_ranking] société=%s ad=%s: %s',
            company.pk, ad.meta_id, verdict.reason)
        EngineAlert.objects.create(
            company=company, alert_type=ALERT_GUARDRAIL,
            message=f"Ad « {ad.name or ad.meta_id} » : {verdict.reason}",
            severity=EngineAlert.Severity.CRITIQUE, entity_key=entity_key,
            detail={'guard': 'quality_ranking', 'ad_meta_id': ad.meta_id,
                    **verdict.computed})
        emitted += 1
    return emitted


@shared_task(name='adsengine.evaluate_guardrails')
def evaluate_guardrails():
    """ADSENG15 — Boucle CRITIQUE du Gardien (toutes les 6 h).

    Évalue les règles de cadence critique (zéro-diffusion, ad refusée, pic/chute
    de dépense…) sur chaque société active. JAMAIS sub-horaire (les rate limits
    Meta scalent au spend et pénalisent les petits comptes, dd-guardian §A9).
    NO-OP propre tant qu'aucune ``RulePolicy`` critique n'est activée. Renvoie le
    récapitulatif ``{'companies': n, 'rules_evaluated': m}``."""
    from authentication.selectors import active_companies

    from . import rules_engine

    result = rules_engine.evaluate_all(
        cadences=rules_engine.CRITICAL_CADENCES)
    # PUB32 — quadrant de garde-fous DURS niveau ad (brake-only) : classement de
    # qualité « below_average » soutenu → alerte de frein. Best-effort/isolé.
    guard_alerts = 0
    for company in active_companies():
        try:
            guard_alerts += _evaluate_ranking_guards_for_company(company)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.evaluate_guardrails: échec garde classement '
                'société %s', company.pk, exc_info=True)
    if isinstance(result, dict):
        result['ranking_guard_alerts'] = guard_alerts
    logger.info('adsengine.evaluate_guardrails: %s', result)
    return result


@shared_task(name='adsengine.evaluate_optimization_rules')
def evaluate_optimization_rules():
    """ADSENG15 — Boucle d'OPTIMISATION du Gardien (quotidienne).

    Évalue les règles de cadence quotidienne + hebdomadaire (fatigue créative,
    bande CPL, backlog bas…) après la synchro ENG6. Best-effort par société ;
    idempotent (dédup par cible sur le cooldown). Renvoie le récapitulatif."""
    from . import rules_engine

    result = rules_engine.evaluate_all(
        cadences=rules_engine.OPTIMIZATION_CADENCES)
    logger.info('adsengine.evaluate_optimization_rules: %s', result)
    return result


@shared_task(name='adsengine.run_reward_divergence_check')
def run_reward_divergence_check():
    """PUB15 — Boucle HEBDO du détecteur de divergence CRM/proxy du bandit
    (ADSENG9 ``rewards.run_divergence_check``, resté sans appelant production).

    Pour chaque société active, compare le classement PROXY des bras (conversation
    démarrée / impression) au classement du COÛT CRM (coût-par-lead-qualifié). Une
    divergence ≥2 positions avec ≥10 leads qualifiés cumulés PROPOSE un REBALANCE
    (``EngineAction`` propose-only : ``status=proposee``, ``auto=False``) visible
    dans Approbations — le moteur ne réalloue JAMAIS seul (véto CRM, jamais
    pilotage : approbation humaine requise). Best-effort par société ; NO-OP propre
    sans bras/expérience. Renvoie le nombre de propositions REBALANCE créées."""
    from authentication.selectors import active_companies

    from . import rewards

    proposed = 0
    for company in active_companies():
        try:
            _decision, action = rewards.run_divergence_check(company)
            if action is not None:
                proposed += 1
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.run_reward_divergence_check: échec société %s',
                company.pk, exc_info=True)
            continue
    logger.info(
        'adsengine.run_reward_divergence_check: %s proposition(s) REBALANCE',
        proposed)
    return {'rebalance_proposed': proposed}


@shared_task(name='adsengine.evaluate_quarter_hourly')
def evaluate_quarter_hourly():
    """ADSDEEP42 — Boucle QUART-HORAIRE du Gardien (toutes les 15 min).

    Évalue UNIQUEMENT les ``RulePolicy`` opt-in à cette cadence
    (``cadence_minutes>0``) — jamais toutes les règles critiques : le fondateur
    élève explicitement une règle jugée assez critique pour un rythme de 15 min.

    BORNÉE par le budgeteur de rate-limit ADSDEEP5 : une société dont le compte
    Meta est en throttle (usage connu ≥ seuil) est SAUTÉE ce tick — jamais un 613
    provoqué par la haute fréquence (l'évaluation lit les miroirs locaux, mais une
    proposition auto-appliquable pourrait toucher l'API : on ne tourne pas sur un
    compte déjà contraint). NO-OP propre tant qu'aucune règle n'a opté (0 par
    défaut). Best-effort par société. Renvoie ``{'evaluated', 'throttled_skipped'}``."""
    from authentication.selectors import active_companies

    from . import meta_client, rules_engine
    from .models import MetaConnection

    evaluated = throttled = 0
    for company in active_companies():
        conn = MetaConnection.objects.filter(company=company).first()
        if conn is not None and conn.ad_account_id:
            status = meta_client.rate_limit_status(conn.ad_account_id)
            if status and status.get('throttled'):
                throttled += 1
                continue  # ADSDEEP5 — budget de rate-limit épuisé : on saute
        try:
            evaluated += rules_engine.evaluate_company(
                company, quarter_hourly=True)
        except Exception:  # noqa: BLE001 — isolation par société
            logger.warning(
                'adsengine.evaluate_quarter_hourly: échec société %s',
                getattr(company, 'pk', company), exc_info=True)
            continue

    result = {'evaluated': evaluated, 'throttled_skipped': throttled}
    logger.info('adsengine.evaluate_quarter_hourly: %s', result)
    return result


@shared_task(name='adsengine.run_active_flightplans')
def run_active_flightplans():
    """ADSENG35 — Boucle du FlightRunner (quotidienne, après la synchro ENG6).

    Pour chaque société dont un ``FlightPlan`` est ACTIF, exécute la boucle
    quotidienne du runner — mais UNIQUEMENT si le mode autonome est ACTIVÉ pour
    la société (``is_autonomy_active``, OFF par défaut, posé seulement quand le
    préflight ADSENG38 est vert) ET si l'interrupteur global n'est pas engagé.
    Le lundi, exécute aussi la boucle hebdo + l'avancement de phase.

    NO-OP propre par défaut : tant qu'aucune société n'a activé l'autonomie, ce
    beat ne fait rien (aucun run autonome n'est jamais déclenché sans go-live
    humain). Best-effort par société ; jamais d'unpause programmatique."""
    import datetime as _dt

    from authentication.selectors import active_companies

    from .flightrunner import FlightRunner, is_autonomy_active
    from .models import FlightPlan

    today = _dt.date.today()
    is_monday = today.weekday() == 0
    ran = 0
    for company in active_companies():
        if not is_autonomy_active(company):
            continue  # OFF par défaut : aucun run autonome sans activation verte
        plan = FlightPlan.objects.filter(
            company=company, status=FlightPlan.Statut.ACTIF).first()
        if plan is None:
            continue
        try:
            runner = FlightRunner(plan)
            if runner.is_killed():
                continue  # interrupteur global engagé : no-op
            runner.run_daily(today=today)
            if is_monday:
                runner.run_weekly(today=today)
                runner.advance_phase(today=today)
            ran += 1
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.run_active_flightplans: échec société %s',
                company.pk, exc_info=True)
            continue

    logger.info(
        'adsengine.run_active_flightplans: %s société(s) exécutée(s)', ran)
    return {'companies_ran': ran}


@shared_task(name='adsengine.emit_capi_signatures')
def emit_capi_signatures():
    """ADSDEEP27/28 — Beat quotidien : pousse au CRM Dataset Meta les deux bornes
    de la boucle *Conversion Leads* — l'amont ``lead_received`` (par
    ``MetaLeadMirror``) et l'issue ``signed_contract`` (par deal signé Odoo) —
    idempotents (marqueur ``CapiOdooEvent``). Meta exige AU MOINS deux étapes par
    ``lead_id`` : un lead signé porte donc bien réception + signature.

    NO-OP propre sans ``CAPI_CRM_DATASET_ID`` + token : aucune société n'est
    balayée, aucune lecture Odoo ni appel réseau. Best-effort par société ; une
    société en échec n'empêche jamais les suivantes."""
    from authentication.selectors import active_companies

    from . import capi_odoo

    if not capi_odoo.is_configured():
        logger.info(
            'adsengine.emit_capi_signatures: CRM Dataset non configuré — no-op')
        return {'configured': False, 'received': 0, 'signed': 0}

    received = signed = 0
    for company in active_companies():
        try:
            received += capi_odoo.emit_lead_received(company)['emitted']
            signed += capi_odoo.emit_signed_deals(company)['emitted']
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.emit_capi_signatures: échec société %s',
                company.pk, exc_info=True)
            continue

    logger.info(
        'adsengine.emit_capi_signatures: %s reçu(s), %s signé(s)',
        received, signed)
    return {'configured': True, 'received': received, 'signed': signed}


@shared_task(name='adsengine.run_daily_reconciliation')
def run_daily_reconciliation():
    """PUB19 — Beat QUOTIDIEN : réconcilie Meta vs ERP et PERSISTE un
    ``ReconciliationSnapshot`` par campagne (ADSENG31).

    La fonction persist+alerte de ``reconciliation.py`` était MORTE : seul le CSV
    on-demand appelait ``reconcile`` (calcul sans persistance). Ce beat appelle
    ``reconciliation.run_daily_reconciliation`` qui upserte un snapshot par
    campagne (idempotent par ``(company, date, campaign)``) et, sur une divergence
    NOUVELLE au-delà du seuil (plancher absolu + ratio), émet une ``EngineAlert``
    🟠 « divergence silencieuse » (jamais deux fois pour la même divergence).
    Best-effort par société ; NO-OP propre sans campagne miroir. Renvoie
    ``{'companies', 'snapshots'}``."""
    from authentication.selectors import active_companies

    from . import reconciliation
    from .models import AdCampaignMirror

    companies = 0
    snapshots = 0
    for company in active_companies():
        if not AdCampaignMirror.objects.filter(company=company).exists():
            continue  # rien à réconcilier tant qu'aucune campagne n'est miroitée
        try:
            contract = reconciliation.run_daily_reconciliation(company)
            companies += 1
            snapshots += len(contract.get('campaigns', []))
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.run_daily_reconciliation: échec société %s',
                company.pk, exc_info=True)
            continue

    logger.info(
        'adsengine.run_daily_reconciliation: %s société(s), %s snapshot(s)',
        companies, snapshots)
    return {'companies': companies, 'snapshots': snapshots}


@shared_task(name='adsengine.decay_assumptions_weekly')
def decay_assumptions_weekly():
    """ASG2 — Beat HEBDO : oubli des posteriors de l'arbre d'hypothèses.

    Chaque exécution = une « semaine » (dd-assumption-engine §3.2) : chaque
    ``AssumptionNode`` non testé depuis ≥ 7 jours (et non saisonnier, non retiré)
    s'oublie d'un cran vers son prior, à la demi-vie de sa classe. NO-OP propre
    pour une société sans nœud. Best-effort par société ; la logique pure +
    modèle vit dans ``assumption_decay.py``. Renvoie le nombre total de nœuds
    oubliés."""
    from authentication.selectors import active_companies

    from . import assumption_decay

    total = 0
    for company in active_companies():
        try:
            total += assumption_decay.run_weekly_decay(company)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.decay_assumptions_weekly: échec société %s',
                company.pk, exc_info=True)
            continue
    logger.info(
        'adsengine.decay_assumptions_weekly: %s nœud(s) oublié(s)', total)
    return {'nodes_decayed': total}


@shared_task(name='adsengine.generate_creative_variants')
def generate_creative_variants(base_asset_id, brand_fields=None, count=2):
    """ENG18 — Tâche « variantes » : 2-3 statiques d'un asset de base approuvé.

    Charge l'asset de base, délègue à ``creative_factory.generate_variants``
    (gated fal/Templated — no-op sans clé), et renvoie le nombre de variantes
    créées. Les variantes naissent en policy PENDING, liées au parent. NO-OP
    propre si l'asset est introuvable."""
    from . import creative_factory as cf
    from .models import CreativeAsset

    base = CreativeAsset.objects.filter(id=base_asset_id).first()
    if base is None:
        return {'variants_created': 0}
    variants = cf.generate_variants(
        base, brand_fields=brand_fields, count=count)
    logger.info(
        'adsengine.generate_creative_variants: %s variante(s) pour asset %s',
        len(variants), base_asset_id)
    return {'variants_created': len(variants)}


def _run_grounded_generation(company, seed_brief, *, components=None,
                             max_variants=3, generator=None):
    """PUB16 — Orchestration du pipeline de génération IA ANCRÉE (AGEN2).

    Produit des variantes dont CHAQUE chiffre cite une ``FactEntry`` publiée
    (``generation.generate_grounded_variants``), emballe les assets ancrés (nés
    PENDING, ``policy_stamp={}``) dans un ``CreativeGenerationBatch`` EN_ATTENTE
    et PERSISTE l'audit (``fact_table_version`` + ``claim_verdicts`` par variante,
    via ``generation_audit.record_audit``). L'IA produit des ASSETS, jamais des
    décisions : le lot attend une approbation HUMAINE par lot avant d'entrer au
    backlog (``recombine.approve_lot``). NO-OP propre (``enabled=False``, aucun
    lot) sans clé/générateur. Renvoie un dict de rapport."""
    from . import generation, generation_audit
    from .models import CreativeGenerationBatch

    result = generation.generate_grounded_variants(
        company, seed_brief, components=components, max_variants=max_variants,
        generator=generator, create_assets=True, source_lane='gen')
    if not result.get('enabled'):
        return {'enabled': False, 'batch_id': None, 'assets': 0,
                'reason': result.get('reason', 'génération désactivée')}

    assets = result.get('assets') or []
    batch = CreativeGenerationBatch.objects.create(
        company=company,
        status=CreativeGenerationBatch.Statut.EN_ATTENTE,
        visual_ids=[a.pk for a in assets])
    generation_audit.record_audit(
        batch,
        fact_table_version=result.get('table_version'),
        claim_verdicts={
            'seed_brief': (seed_brief or '').strip()[:200],
            'variants': result.get('variants', []),
            'rejected': result.get('rejected', []),
        })
    logger.info(
        'adsengine._run_grounded_generation: lot %s, %s asset(s) ancré(s), '
        '%s rejeté(s)', batch.pk, len(assets), len(result.get('rejected', [])))
    return {'enabled': True, 'batch_id': batch.pk, 'assets': len(assets),
            'rejected': len(result.get('rejected', [])),
            'table_version': result.get('table_version')}


@shared_task(name='adsengine.generate_grounded_variants')
def generate_grounded_variants(company_id, seed_brief, components=None,
                               max_variants=3):
    """PUB16 — Tâche async : câble le pipeline de génération IA ANCRÉE (AGEN2 :
    ``generation→claim_check→groundedness→generation_audit``) resté sans point
    d'entrée production. Key-gated : sans ``ADSENGINE_GEN_API_KEY`` (et sans
    générateur), NO-OP propre (``enabled=False``, aucun lot, zéro crash) ; sinon
    crée un ``CreativeGenerationBatch`` EN_ATTENTE de variantes ancrées FactTable
    + audit ``claim_verdicts`` persisté. NO-OP propre si société introuvable."""
    from authentication.models import Company

    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return {'enabled': False, 'batch_id': None, 'assets': 0,
                'reason': 'société introuvable'}
    return _run_grounded_generation(
        company, seed_brief, components=components, max_variants=max_variants)


# ─────────────────────────────────────────────────────────────────────────────
# lane/gen-b — AGEN8 : auto-pause maison du rayon d'explosion (§10.2 point 5).
# Bloc ISOLÉ (fold propre avec le co-éditeur de tasks.py) — n'ajouter ici que
# des tâches du rayon d'explosion.
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(name='adsengine.autopause_blast_radius')
def autopause_blast_radius():
    """AGEN8 — Boucle d'auto-pause maison (polling court, dd-assumption-engine
    §10.2 point 5).

    Pour chaque société active, POLLE ``effective_status`` (miroir local) des
    créatifs GÉNÉRÉS et met en PAUSE ceux désapprouvés par Meta — dans le cycle
    courant (Meta n'offre AUCUNE auto-pause native : absence vérifiée). Un client
    live (connexion Meta + token) émet la pause réelle ; sans client, le bras est
    quand même retiré du bandit + une alerte 🔴 est levée (jamais un échec
    silencieux). Best-effort par société. NO-OP propre tant qu'aucun créatif
    généré n'est surveillé. Renvoie ``{'companies', 'paused', 'alerted'}``."""
    from authentication.selectors import active_companies

    from . import blast_radius, meta_client
    from .models import MetaConnection

    companies = paused = alerted = 0
    for company in active_companies():
        companies += 1
        client = None
        conn = MetaConnection.objects.filter(company=company).first()
        if conn is not None and conn.has_token:
            try:
                client = meta_client.MetaClient.from_connection(conn)
            except Exception:  # pragma: no cover - défensif (token invalide)
                client = None
        try:
            summary = blast_radius.poll_and_autopause(company, client=client)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.autopause_blast_radius: échec société %s',
                getattr(company, 'pk', company), exc_info=True)
            continue
        paused += summary['paused']
        alerted += summary['alerted']

    result = {'companies': companies, 'paused': paused, 'alerted': alerted}
    logger.info('adsengine.autopause_blast_radius: %s', result)
    return result
