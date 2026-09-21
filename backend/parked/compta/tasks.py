"""Tâches Celery de l'app compta — auto-découvertes par `erp_agentique.celery`
(`app.autodiscover_tasks()`), aucun enregistrement manuel requis.
"""
from celery import shared_task

from .models import Campagne
from .services import (
    decider_gagnant_ab, envoyer_campagnes_planifiees, executer_etapes_dues,
    recalculer_dormants, envoyer_communications_evenement_dues,
    traiter_posts_sociaux_dus,
)


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


@shared_task(name='compta.envoyer_campagnes_planifiees')
def envoyer_campagnes_planifiees_task():
    """XMKT7 — Enveloppe Celery Beat : envoie chaque campagne planifiée dont
    l'échéance est atteinte, par lots throttlés + fenêtres de silence.
    """
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        total += len(envoyer_campagnes_planifiees(company))
    return {'campagnes_envoyees': total}


@shared_task(name='compta.decider_gagnants_ab')
def decider_gagnants_ab_task():
    """XMKT14 — Enveloppe Celery Beat : décide le gagnant A/B de chaque
    campagne envoyée avec un test A/B en cours dont la fenêtre est écoulée.
    """
    decisions = 0
    qs = Campagne.objects.filter(
        statut=Campagne.Statut.ENVOYEE, ab_gagnant='').exclude(ab_test={})
    for campagne in qs:
        if decider_gagnant_ab(campagne):
            decisions += 1
    return {'decisions': decisions}


@shared_task(name='compta.recalculer_dormants_marketing')
def recalculer_dormants_task():
    """XMKT22 — Enveloppe Celery Beat : recalcule le statut d'engagement
    (dormant/actif) de chaque société ayant une fenêtre sunset configurée.
    """
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        total += recalculer_dormants(company)
    return {'contacts_dormants': total}


@shared_task(name='compta.envoyer_communications_evenement')
def envoyer_communications_evenement_task():
    """ZMKT17 — Enveloppe Celery Beat : envoie chaque communication
    d'événement dont l'échéance est atteinte."""
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        total += len(envoyer_communications_evenement_dues(company))
    return {'communications_envoyees': total}


@shared_task(name='compta.traiter_posts_sociaux')
def traiter_posts_sociaux_task():
    """XMKT35 — Enveloppe Celery Beat : traite les posts sociaux à échéance,
    société par société. Sans jeton Meta Graph : rappel manuel notifié une
    fois (texte prêt à coller) ; avec jeton : publication réelle gated."""
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        total += len(traiter_posts_sociaux_dus(company))
    return {'posts_traites': total}


# NTTRE29/31 — enregistre les tâches Beat trésorerie (scheduled.py) auprès de
# Celery via ce module tasks.py auto-découvert (autodiscover_tasks).
from . import scheduled  # noqa: E402,F401
