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


@shared_task(name='crm.escalader_rappels_demandes')
def escalader_rappels_demandes_task():
    """QW4 — Enveloppe Celery Beat de la commande de gestion homonyme.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Escalade
    les rappels demandés (``contact_preference=phone_ok``) non actionnés au-
    delà du SLA rappel — plus serré que le SLA générique premier-contact de
    ``recycler_leads_non_travailles``. Même patron : réutilise entièrement la
    commande de gestion (testable hors Celery via
    ``manage.py escalader_rappels_demandes``).
    """
    from apps.crm.management.commands.escalader_rappels_demandes import (
        escalader_rappels_demandes,
    )
    escalated = escalader_rappels_demandes()
    return {'escalated': escalated}


@shared_task(name='crm.snapshot_forecast_hebdo')
def snapshot_forecast_hebdo_task():
    """NTCRM6 — Enveloppe Celery Beat de la commande de gestion homonyme.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Crée/
    upsert le snapshot forecast hebdomadaire (idempotent par semaine ISO +
    owner). Même patron : réutilise entièrement la commande de gestion
    (testable hors Celery via ``manage.py snapshot_forecast_hebdo``).
    """
    from apps.crm.management.commands.snapshot_forecast_hebdo import (
        snapshot_forecast_hebdo,
    )
    nb = snapshot_forecast_hebdo()
    return {'snapshots': nb}


@shared_task(name='crm.recalculer_scores_obsoletes')
def recalculer_scores_obsoletes_task():
    """CRX22 — Enveloppe Celery Beat du rafraîchissement quotidien des scores.

    Planifiée dans ``erp_agentique/celery.py`` (``beat_schedule``). Le score
    n'était recalculé qu'à l'édition : la décote de RÉCENCE ne s'appliquait
    donc jamais aux leads dormants, qui gardaient le score de leur premier
    jour. Délègue entièrement au service (testable hors Celery via
    ``apps.crm.services.recalculer_scores_obsoletes``).
    """
    from apps.crm.services import recalculer_scores_obsoletes

    return recalculer_scores_obsoletes()
