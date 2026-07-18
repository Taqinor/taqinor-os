"""Tâches Celery de l'app fiscal — auto-découvertes par ``erp_agentique.celery``
(``app.autodiscover_tasks()``), aucun enregistrement manuel requis.

WIR25 — la commande ``rappels_fiscaux`` (NTMAR15 : échéances CNSS/taxe pro/TVA/
IS…) existait mais n'était JAMAIS planifiée au beat : elle ne tournait que
lancée à la main. Cette enveloppe mince la câble au beat (voir
``erp_agentique/celery.py`` → clé ``fiscal-rappels-fiscaux``, quotidien, heure
creuse) et est routée vers la file ``scheduled`` (``settings/base.py``).
"""
from celery import shared_task


@shared_task(name='fiscal.rappels_fiscaux')
def rappels_fiscaux_task():
    """WIR25 (NTMAR15) — Enveloppe Beat : rappels d'échéance fiscale N jours
    avant la date limite (CNSS/taxe pro/TVA/IS…), TOUTES sociétés en une passe.

    IDEMPOTENT via ``EcheanceFiscale.rappel_envoye_le`` : deux exécutions le
    même jour ne renotifient jamais (aucun double envoi). Best-effort, jamais
    bloquant. Renvoie le nombre de rappels envoyés.
    """
    from apps.fiscal.services import envoyer_rappels_fiscaux

    return len(envoyer_rappels_fiscaux())
