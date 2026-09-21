"""AOF71 — le job d'ingestion d'un support de plan, suivi par ``BackgroundJob``.

Dispatch par ``core.jobs.submit('ao_ingestion_plan', …)`` — jamais un suivi de
progression maison : la progression, l'échec et la clé du livrable sont ceux de
la plateforme (NTPLT29), donc le même écran suit un import de plan, un export
lourd et un import de données.

La tâche prend des CLÉS PRIMAIRES (garde ``scripts/check_celery_tasks.py``) et
n'a qu'une seule issue par exécution : ``done`` ou ``failed`` avec un motif
FRANÇAIS — jamais un job laissé ``running``.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

__all__ = ['KIND_INGESTION_PLAN', 'ingerer_plan', 'lancer_ingestion_plan']

#: Type logique du job (``BackgroundJob.kind``).
KIND_INGESTION_PLAN = 'ao_ingestion_plan'


@shared_task(name='ao.ingerer_plan')
def ingerer_plan(job_id=None, company_id=None, plan_source_id=None, page=None,
                 dpi=None, user_id=None):
    """Rasterise/normalise le support d'un ``PlanSource`` et publie le rendu.

    IDEMPOTENTE : rejouer la tâche retrouve le rendu par son nom déterministe
    (``plan-<pk>-p<page>.png``) et ne téléverse rien de neuf.
    """
    from core.models import BackgroundJob

    from . import ingestion_service
    from .models import PlanSource

    job = BackgroundJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.info('ao.ingerer_plan : job #%s introuvable', job_id)
        return {'statut': 'inconnu'}

    try:
        job.marquer_progression(5)
        plan_source = PlanSource.objects.filter(
            pk=plan_source_id, company=job.company).select_related(
                'attachment', 'toiture').first()
        if plan_source is None:
            raise ingestion_service.IngestionImpossible(
                "Support de plan introuvable dans cette société.")

        resultat = ingestion_service.ingerer_plan_source(
            plan_source, page=page,
            dpi=dpi or ingestion_service.DPI_DEFAUT,
            user=job.user, progression=job.marquer_progression)
        job.marquer_termine(resultat.get('file_key', ''))
        return dict(resultat, statut='done')
    except Exception as erreur:  # noqa: BLE001 — toute panne = échec PROPRE
        logger.exception('ao.ingerer_plan : échec du job #%s', job_id)
        job.marquer_echec(str(erreur))
        return {'statut': 'failed', 'motif': str(erreur)}


def lancer_ingestion_plan(plan_source, *, user, page=None, dpi=None):
    """Soumet l'ingestion d'un support à ``core.jobs`` et rend le job créé.

    Point d'entrée unique : la société et l'utilisateur sont ceux du
    ``PlanSource`` et de l'appelant, jamais lus d'un corps de requête.
    """
    from core.jobs import submit

    return submit(KIND_INGESTION_PLAN, ingerer_plan,
                  company=plan_source.company, user=user,
                  plan_source_id=plan_source.pk, page=page, dpi=dpi,
                  user_id=getattr(user, 'pk', None))
