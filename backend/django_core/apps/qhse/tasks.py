"""Tâches Celery de l'app QHSE — auto-découvertes par `erp_agentique.celery`
(`app.autodiscover_tasks()`), aucun enregistrement manuel requis.
"""
from celery import shared_task


@shared_task(name='qhse.escalader_checkins_en_retard')
def escalader_checkins_en_retard_task():
    """XFSM24 — Enveloppe Celery Beat du service homonyme.

    Délègue entièrement au service (même logique, testable en dehors de
    Celery via un appel direct de fonction).
    """
    from apps.qhse.services import escalader_checkins_en_retard
    escalades = escalader_checkins_en_retard()
    return {'escalades': [c.id for c in escalades]}
