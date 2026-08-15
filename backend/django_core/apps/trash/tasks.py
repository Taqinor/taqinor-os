"""NTUX29 — planification Celery beat de la purge de rétention (NTUX7).

Autodécouvert par `erp_agentique.celery` (`autodiscover_tasks()`), comme
`apps.ged.tasks`. Toute la logique métier vit dans `services.purger_expires`
(testable sans Celery) ; cette tâche n'est qu'une fine enveloppe planifiable,
enregistrée quotidiennement (03h00 Africa/Casablanca) dans
`erp_agentique/celery.py` `beat_schedule`.
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='trash.purger_corbeille_transverse')
def purger_corbeille_transverse():
    """NTUX29 — supprime DÉFINITIVEMENT les `ElementSupprime` dont `expire_le`
    est dépassé (rétention 30 jours, NTUX7). Journalise le nombre purgé par
    société. Idempotent — rejouer sans nouvelle entrée expirée ne purge rien."""
    from . import services

    par_company = services.purger_expires(now=timezone.now())
    for company_id, nombre in sorted(par_company.items()):
        logger.info(
            'trash.purger_corbeille_transverse: société %s — %d entrée(s) purgée(s).',
            company_id, nombre)
    total = sum(par_company.values())
    logger.info(
        'trash.purger_corbeille_transverse: total %d entrée(s) purgée(s) sur %d société(s).',
        total, len(par_company))
    return par_company
