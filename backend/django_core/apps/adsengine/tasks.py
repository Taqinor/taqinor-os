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

    sync.sync_campaigns(company, client.get_campaigns())
    sync.sync_adsets(company, client.get_adsets())
    sync.sync_ads(company, client.get_ads())

    today = datetime.date.today()
    for camp in AdCampaignMirror.objects.filter(company=company):
        for row in client.get_insights(camp.meta_id):
            day = _parse_date(row.get('date_start')) or today
            sync.upsert_insight(
                company, camp, date=day,
                spend=row.get('spend'), results=row.get('results'),
                frequency=row.get('frequency'), cpl=row.get('cpl'))


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
