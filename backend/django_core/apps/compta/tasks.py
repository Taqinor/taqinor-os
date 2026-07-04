"""Tâches Celery de l'app compta — auto-découvertes par `erp_agentique.celery`
(`app.autodiscover_tasks()`), aucun enregistrement manuel requis.
"""
from celery import shared_task

from .services import executer_etapes_dues


@shared_task(name='compta.executer_sequences_relance')
def executer_sequences_relance_task():
    """XMKT1 — Enveloppe Celery Beat : exécute les étapes dues de toutes les
    inscriptions actives, société par société. Gated/idempotent (voir
    ``services.executer_etapes_dues`` / ``_executer_une_etape`` — aucun envoi
    réel tant qu'aucune intégration n'est active).
    """
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        total += len(executer_etapes_dues(company))
    return {'executions': total}
