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


@shared_task(name='qhse.relancer_csh_du_jour')
def relancer_csh_du_jour_task():
    """PACT184 (XQHS12) — Enveloppe Celery Beat du service homonyme (rappel
    légal de réunion CSH trimestrielle, Code du travail — ``csh_relance_due``
    n'avait aucun appelant avant cette tâche).
    """
    from apps.qhse.services import relancer_csh_du_jour
    relancees = relancer_csh_du_jour()
    return {'relancees': [c.id for c in relancees]}
