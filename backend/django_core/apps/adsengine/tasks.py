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
