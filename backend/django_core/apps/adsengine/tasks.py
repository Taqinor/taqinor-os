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
    'video_p25_watched_actions', 'video_p50_watched_actions',
    'video_p75_watched_actions', 'video_p95_watched_actions',
    'video_p100_watched_actions', 'video_play_actions',
    'video_6_sec_watched_actions', 'video_15_sec_watched_actions',
    'video_30_sec_watched_actions', 'video_thruplay_watched_actions',
    'video_avg_time_watched_actions',
)

# Fenêtre glissante (jours) pour la synchro ad/adset — les insights fins sont
# lus sur les 7 derniers jours (le détail campagne reste sur ``maximum``).
AD_INSIGHT_WINDOW_DAYS = 7


def _account_node(conn):
    """Nœud de compte publicitaire (``act_<id>``) depuis la connexion, ou ''."""
    acct = str(conn.ad_account_id or '').strip()
    if not acct:
        return ''
    return acct if acct.startswith('act_') else f'act_{acct}'


def _sync_level_insights(company, conn, client, *, level):
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
    id_field = 'ad_id' if level == 'ad' else 'adset_id'
    mirror_model = AdMirror if level == 'ad' else AdSetMirror
    today = datetime.date.today()
    since = today - datetime.timedelta(days=AD_INSIGHT_WINDOW_DAYS - 1)
    rows = client.get_insights(
        node,
        fields=AD_INSIGHT_FIELDS + (id_field,),
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
        sync.upsert_insight(
            company, mirror, date=day,
            spend=norm['spend'], results=norm['results'],
            frequency=norm['frequency'], cpl=norm['cpl'],
            impressions=norm['impressions'], reach=norm['reach'],
            clicks=norm['clicks'], link_clicks=norm['link_clicks'],
            conversations=norm['conversations'],
            leads_count=norm['leads_count'],
            video_metrics=norm['video_metrics'])


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

    # ADSDEEP2 — snapshots niveau adset PUIS ad (edge compte, level=…). Placés
    # AVANT la boucle campagne pour que le dernier appel get_insights reste
    # celui de la campagne (fenêtre ``maximum`` — contrat ENG6 préservé).
    _sync_level_insights(company, conn, client, level='adset')
    _sync_level_insights(company, conn, client, level='ad')

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

    from .meta_client import MetaClient
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
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'adsengine.sync_breakdowns_weekly: échec société %s',
                company.pk, exc_info=True)
            continue
    logger.info(
        'adsengine.sync_breakdowns_weekly: %s campagne(s) traitée(s)',
        processed)
    return {'campaigns_processed': processed}


@shared_task(name='adsengine.sync_insights_daily')
def sync_insights_daily():
    """ENG6 — Synchro quotidienne des insights, société par société.

    NO-OP propre tant qu'aucune ``MetaConnection`` n'est active + tokenisée
    (``is_live``) : la société est sautée sans aucun appel réseau. Best-effort
    par société ; renvoie le nombre de sociétés réellement synchronisées.
    """
    from authentication.selectors import active_companies

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


@shared_task(name='adsengine.evaluate_guardrails')
def evaluate_guardrails():
    """ADSENG15 — Boucle CRITIQUE du Gardien (toutes les 6 h).

    Évalue les règles de cadence critique (zéro-diffusion, ad refusée, pic/chute
    de dépense…) sur chaque société active. JAMAIS sub-horaire (les rate limits
    Meta scalent au spend et pénalisent les petits comptes, dd-guardian §A9).
    NO-OP propre tant qu'aucune ``RulePolicy`` critique n'est activée. Renvoie le
    récapitulatif ``{'companies': n, 'rules_evaluated': m}``."""
    from . import rules_engine

    result = rules_engine.evaluate_all(
        cadences=rules_engine.CRITICAL_CADENCES)
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
