"""Tâches Celery de la couche fondation ``core`` (autodécouvertes par
``erp_agentique.celery`` comme ``apps.ventes.tasks``).

  * YOPSB1 — ``core.dump_database`` : pg_dump quotidien réel vers MinIO
    (03:00 Africa/Casablanca), journalisé en ``BackupRun``.
  * YOPSB2 — ``core.restore_drill`` : drill de restauration hebdomadaire
    (lundi 04:00), restaure le dernier dump dans une base JETABLE et vérifie
    des comptages clés — jamais la base de production.
  * YOPSB3 — ``core.purge_backups`` : purge GFS quotidienne des dumps
    (05:00), DRY-RUN tant que ``BACKUP_PURGE_AUTO_APPLY`` n'est pas activé.

Toute la logique vit dans ``core.backup`` (testable sans Celery) ; ces
tâches ne sont qu'une fine enveloppe planifiable, comme les autres tâches du
dépôt (cf. apps/ged/tasks.py)."""
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
