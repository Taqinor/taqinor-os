"""Tâches Celery de la couche fondation ``core`` (autodécouvertes par
``erp_agentique.celery`` comme ``apps.ventes.tasks``).

  * YOPSB1 — ``core.dump_database`` : pg_dump quotidien réel vers MinIO
    (03:00 Africa/Casablanca), journalisé en ``BackupRun``.
  * YOPSB2 — ``core.restore_drill`` : drill de restauration hebdomadaire
    (lundi 04:00), restaure le dernier dump dans une base JETABLE et vérifie
    des comptages clés — jamais la base de production.
  * YOPSB3 — ``core.purge_backups`` : purge GFS quotidienne des dumps
    (05:00), DRY-RUN tant que ``BACKUP_PURGE_AUTO_APPLY`` n'est pas activé.
  * YOPSB10 — ``core.run_retention`` : sweep quotidien (02:00) de TOUTES les
    politiques de rétention enregistrées (``core.retention``), DRY-RUN tant
    que ``RETENTION_AUTO_APPLY`` n'est pas activé.
  * YHARD6 — ``core.beat_heartbeat`` : tick fréquent (toutes les 5 min) qui
    écrit un timestamp dans le cache (``core.metrics.mark_beat_heartbeat``) —
    permet à ``/metrics`` et ``core/health.py`` de détecter un beat arrêté.

Toute la logique vit dans ``core.backup``/``core.retention`` (testable sans
Celery) ; ces tâches ne sont qu'une fine enveloppe planifiable, comme les
autres tâches du dépôt (cf. apps/ged/tasks.py)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='core.dump_database')
def dump_database_task():
    """YOPSB1 — pg_dump quotidien réel vers MinIO (planifié 03:00)."""
    from core.models import BackupRun

    from . import backup

    run = BackupRun.objects.create(
        kind=BackupRun.KIND_DB_DUMP, mode=BackupRun.MODE_PLANIFIE,
        company=None)
    run = backup.dump_database(run)
    logger.info('core.dump_database: statut=%s run=%s', run.statut, run.pk)
    return {'statut': run.statut, 'run_id': run.pk}


@shared_task(name='core.restore_drill')
def restore_drill_task():
    """YOPSB2 — drill de restauration hebdomadaire (planifié lundi 04:00)."""
    from core.models import BackupRun

    from . import backup

    run = BackupRun.objects.create(
        kind=BackupRun.KIND_RESTORE_DRILL, mode=BackupRun.MODE_PLANIFIE,
        company=None)
    run = backup.restore_drill(run)
    logger.info('core.restore_drill: statut=%s run=%s', run.statut, run.pk)
    return {'statut': run.statut, 'run_id': run.pk}


@shared_task(name='core.purge_backups')
def purge_backups_task():
    """YOPSB3 — purge GFS quotidienne des dumps (planifié 05:00).

    DRY-RUN par défaut (``settings.BACKUP_PURGE_AUTO_APPLY``) : ne supprime
    rien tant que le drapeau n'est pas explicitement vrai."""
    from django.conf import settings

    from . import backup

    apply_ = bool(getattr(settings, 'BACKUP_PURGE_AUTO_APPLY', False))
    result = backup.purger_backups(apply_=apply_)
    logger.info('core.purge_backups: apply=%s conserves=%d supprimes=%d',
                apply_, result['conserves'], result['supprimes'])
    return result


@shared_task(name='core.run_retention')
def run_retention_task():
    """YOPSB10 — sweep quotidien de toutes les politiques de rétention
    enregistrées (planifié 02:00). DRY-RUN par défaut
    (``settings.RETENTION_AUTO_APPLY``) : chaque politique reçoit
    ``apply_=False`` tant que le drapeau n'est pas explicitement vrai."""
    from django.conf import settings

    from . import retention

    apply_ = bool(getattr(settings, 'RETENTION_AUTO_APPLY', False))
    results = retention.run_all_policies(apply_=apply_)
    logger.info('core.run_retention: apply=%s policies=%d',
                apply_, len(results))
    return results


@shared_task(name='core.beat_heartbeat')
def beat_heartbeat_task():
    """YHARD6 — tick de heartbeat du beat (planifié toutes les 5 min).

    Écrit best-effort un timestamp dans le cache ; consommé par
    ``core.metrics.beat_heartbeat_age_seconds`` (endpoint ``/metrics``) et par
    ``core/health.py`` (statut ``degraded`` si le beat est arrêté)."""
    from . import metrics

    metrics.mark_beat_heartbeat()
    return {'ok': True}


@shared_task(name='core.dispatch_outbox')
def dispatch_outbox_task():
    """NTPLT10 — livraison des événements outbox aux handlers durables.

    Filet beat (toutes les 5 min) en plus de l'enqueue immédiat on_commit :
    livre les événements ``pending``/``failed`` échus, applique retries
    exponentiels bornés puis dead-letter. Idempotente (re-run ne double-livre
    pas — dédup ``ProcessedEvent``). Queue ``default``."""
    from . import dispatch_outbox

    counts = dispatch_outbox.dispatch_pending()
    logger.info('core.dispatch_outbox: livrés=%d échecs=%d dead=%d',
                counts['delivered'], counts['failed'], counts['dead'])
    return counts


@shared_task(name='core.scan_live_isolation')
def scan_live_isolation_task():
    """NTPLT8 — scan mensuel DRY-RUN d'étanchéité des DONNÉES vivantes.

    Vérifie sur la base RÉELLE qu'aucune ligne des tables company-scopées n'a un
    ``company_id`` NULL ou orphelin (société supprimée). Complète YRBAC12 (qui
    teste le CODE en CI) par un contrôle des DONNÉES en prod. Ne modifie rien ;
    remonte les anomalies aux admins + audit via le reporteur enregistré."""
    from . import tenant_isolation_scan

    report = tenant_isolation_scan.scan_live_isolation()
    logger.info('core.scan_live_isolation: %d anomalie(s) sur %d table(s)',
                report['anomalies'], report['scanned'])
    return {'anomalies': report['anomalies'], 'scanned': report['scanned']}


@shared_task(name='core.ensure_partitions')
def ensure_partitions_task():
    """NTPLT36 — maintenance des partitions mensuelles À L'AVANCE.

    Crée le mois courant + M+1/M+2 de chaque table partitionnée enregistrée
    (``core.partitioning``), pour qu'une insertion future ait toujours sa
    partition prête. Idempotent (re-run ne recrée rien). Queue ``scheduled``."""
    from . import ensure_partitions

    results = ensure_partitions.ensure_all()
    logger.info('core.ensure_partitions: %d table(s) maintenue(s)',
                len(results))
    return {t: len(p) for t, p in results.items()}


@shared_task(name='core.snapshot_tenant_usage')
def snapshot_tenant_usage_task():
    """NTPLT6 — instantané NOCTURNE d'usage par tenant (metering).

    Une ligne ``TenantUsageSnapshot`` par (société, jour), idempotente (un
    re-run du jour met à jour la même ligne). Comptages BORNÉS. Fondation de
    N100 (plans/billing, différé). Queue ``scheduled`` (tâche planifiée)."""
    from . import usage

    done = usage.snapshot_all()
    logger.info('core.snapshot_tenant_usage: %d société(s) mesurée(s)',
                len(done))
    return {'companies': len(done)}


@shared_task(name='core.purge_idempotency_records')
def purge_idempotency_records_task():
    """YAPIC10 — purge quotidienne des ``IdempotencyRecord`` (YAPIC9) plus
    vieux que 24 h (fenêtre alignée sur la pratique Stripe pour
    ``Idempotency-Key``, documentée dans ``docs/api-conventions.md``).

    Idempotente (un re-run ne supprime rien de plus) et company-agnostique
    (purge par ``created_at``, jamais par société — une clé d'idempotence
    n'a plus de sens à rejouer passé la fenêtre, quel que soit le tenant).
    Queue ``scheduled``."""
    from django.utils import timezone

    from .idempotency import IdempotencyRecord

    cutoff = timezone.now() - timezone.timedelta(hours=24)
    deleted, _ = IdempotencyRecord.objects.filter(
        created_at__lt=cutoff).delete()
    logger.info('core.purge_idempotency_records: supprimés=%d', deleted)
    return {'deleted': deleted}
