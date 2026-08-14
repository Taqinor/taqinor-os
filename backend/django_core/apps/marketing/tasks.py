"""Tâches Celery de l'app marketing — auto-découvertes par
``erp_agentique.celery`` (``app.autodiscover_tasks()``), aucun enregistrement
manuel requis.
"""
from celery import shared_task

from .services import (
    executer_journeys_dus,
    purger_tokens_expires,
    rappeler_approbations_envoi_en_attente,
)


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


@shared_task(name='marketing.purger_tokens_expires')
def purger_tokens_expires_task():
    """NTMKT33 — purge quotidienne (03:00) des jetons publics expirés
    (désinscription XMKT3 / préférences NTMKT22, +90 jours) — voir la
    docstring de ``services.purger_tokens_expires`` : les jetons sont signés
    et jamais stockés, leur expiration est déjà imposée à la lecture."""
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        total += purger_tokens_expires(company).get('jetons_purges', 0)
    return {'jetons_purges': total}


@shared_task(name='marketing.rappeler_approbations_envoi')
def rappeler_approbations_envoi_task():
    """NTMKT35 — rappelle (toutes les 4h) les approbateurs d'un envoi de
    campagne en attente depuis plus de 24h — une seule relance par demande."""
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        total += len(rappeler_approbations_envoi_en_attente(company))
    return {'rappels': total}
