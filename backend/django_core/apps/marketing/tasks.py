"""Tâches Celery de l'app marketing — auto-découvertes par
``erp_agentique.celery`` (``app.autodiscover_tasks()``), aucun enregistrement
manuel requis.
"""
from celery import shared_task

from .services import executer_journeys_dus


@shared_task(name='marketing.executer_journeys')
def executer_journeys_task():
    """NTMKT12 — Enveloppe Celery Beat : fait avancer les inscriptions des
    séquences EN GRAPHE, société par société.

    Complément strict du tick linéaire ``compta.executer_sequences_relance``
    (XMKT1), qui reste seul en charge des séquences sans nœud : une société
    sans aucun graphe est un no-op complet ici.
    """
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        total += len(executer_journeys_dus(company))
    return {'executions': total}
