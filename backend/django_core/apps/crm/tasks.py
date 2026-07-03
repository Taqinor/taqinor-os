"""Tâches Celery de l'app CRM — auto-découvertes par `erp_agentique.celery`
(`app.autodiscover_tasks()`), aucun enregistrement manuel requis.
"""
from celery import shared_task


@shared_task(name='crm.recycler_leads_non_travailles')
def recycler_leads_non_travailles_task():
    """YLEAD14 — Enveloppe Celery Beat de la commande de gestion homonyme.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Délègue
    entièrement à la commande de gestion (même logique, testable en dehors de
    Celery via ``manage.py recycler_leads_non_travailles``).
    """
    from apps.crm.management.commands.recycler_leads_non_travailles import (
        recycler_leads_non_travailles,
    )
    escalated, deassigned = recycler_leads_non_travailles()
    return {'escalated': escalated, 'deassigned': deassigned}
