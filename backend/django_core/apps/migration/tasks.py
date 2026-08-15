"""apps.migration.tasks — jobs Celery beat du groupe NTMIG.

Enregistrés dans ``erp_agentique/celery.py::beat_schedule`` ET dans
``CELERY_TASK_ROUTES`` (settings/base.py, queue ``scheduled``) — une tâche
planifiée laissée sur la queue par défaut serait consommée par le mauvais
worker.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='migration.purger_fichiers_migration')
def purger_fichiers_migration():
    """NTMIG35 — purge des fichiers source (PII) des projets clôturés.

    Quotidien, best-effort, jamais bloquant : les rapports de réconciliation
    (agrégats non-PII) sont conservés, seuls les fichiers téléversés sont
    supprimés du stockage objet.
    """
    from . import services

    resultat = services.purger_fichiers_expires()
    if resultat['fichiers']:
        logger.info(
            'NTMIG35 — %s fichier(s) source purgé(s) sur %s projet(s).',
            resultat['fichiers'], resultat['projets'])
    return resultat
