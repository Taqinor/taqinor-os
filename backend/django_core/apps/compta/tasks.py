"""Tâches Celery de l'app compta — auto-découvertes par `erp_agentique.celery`
(`app.autodiscover_tasks()`), aucun enregistrement manuel requis.
"""
from celery import shared_task

from .models import Campagne
from .services import (
    decider_gagnant_ab, envoyer_campagnes_planifiees, executer_etapes_dues,
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
