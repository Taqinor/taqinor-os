"""Tâches planifiées (Celery Beat) de l'app compta — trésorerie (NTTRE29/31).

Suit le pattern de ``apps/ventes/scheduled.py`` : des tâches ``@shared_task``
idempotentes, société par société, en heure Africa/Casablanca. Enregistrées au
beat schedule dans ``erp_agentique/celery.py`` et routées vers la file
``scheduled`` dans ``settings/base.py``. Importé par ``apps/compta/tasks.py``
(lui-même auto-découvert) pour garantir l'enregistrement des tâches.

  * NTTRE29 — ``recalculer_alerte_rupture`` : recalcule quotidiennement la date
    de rupture de trésorerie (NTTRE18) par société et notifie UNIQUEMENT si une
    rupture apparaît dans ``delai_alerte_rupture_jours`` (NTTRE27), dé-doublonné
    par jour (deux exécutions le même jour = une seule notification).
  * NTTRE31 — ``relances_tresorerie_du_jour`` : câble
    ``services.declencher_relances_du_jour`` (NTTRE11), idempotent.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='compta.recalculer_alerte_rupture')
def recalculer_alerte_rupture():
    """NTTRE29 — Recalcule la date de rupture et notifie si imminente (dedup/jour).

    Idempotent : une seconde exécution le même jour ne re-notifie pas (dedup via
    l'existence d'une notification de rupture émise le jour même). Renvoie le
    nombre de sociétés notifiées.
    """
    from django.utils import timezone

    from authentication.models import Company
    from . import selectors, services

    aujourdhui = timezone.localdate()
    notifiees = 0
    try:
        from apps.notifications.models import EventType, Notification
        from apps.notifications.services import notify
    except Exception:  # pragma: no cover - notifications indisponibles
        return 0

    for company in Company.objects.filter(actif=True):
        params = services.get_parametres_tresorerie(company)
        prev = selectors.previsionnel_tresorerie(company)
        rupture = prev.get('date_rupture_estimee')
        if not rupture:
            continue
        delai = params.delai_alerte_rupture_jours or 14
        if (rupture - aujourdhui).days > delai:
            continue
        lien = '/compta/tresorerie?rupture=1'
        event = EventType.FLOTTE_BUDGET_DEPASSEMENT
        if Notification.objects.filter(
                company=company, event_type=event, link=lien,
                created_at__date=aujourdhui).exists():
            continue
        destinataires = services._destinataires_alerte_tresorerie(company, None)
        titre = 'Rupture de trésorerie prévue'
        corps = f'Rupture de trésorerie estimée au {rupture}.'
        for dest in destinataires:
            notify(dest, event, titre, body=corps, link=lien, company=company)
        if destinataires:
            notifiees += 1
    return notifiees


@shared_task(name='compta.relances_tresorerie_du_jour')
def relances_tresorerie_du_jour():
    """NTTRE31 — Déclenche les relances de recouvrement dues (NTTRE11), par
    société. Idempotent (``declencher_relances_du_jour`` résout un seul palier
    par facture éligible). Renvoie le nombre total de déclenchements."""
    from authentication.models import Company
    from . import services

    total = 0
    for company in Company.objects.filter(actif=True):
        total += len(services.declencher_relances_du_jour(company))
    return total


@shared_task(name='compta.generer_ecritures_recurrentes')
def generer_ecritures_recurrentes_dues():
    """WIR25 (XACC8) — Enveloppe Beat : génère les écritures dues des
    abonnements récurrents actifs (loyer mensuel, abonnements…) en BROUILLON,
    société par société.

    IDEMPOTENT par période (``services.generer_ecritures_recurrentes`` ne
    duplique jamais une écriture déjà générée pour une période) : rejouer le
    même jour ne crée rien de plus (aucun double envoi). No-op tant qu'aucun
    ``AbonnementEcriture`` n'est configuré. Renvoie le nombre total d'écritures
    générées."""
    from authentication.models import Company
    from . import services

    total = 0
    for company in Company.objects.filter(actif=True):
        resultat = services.generer_ecritures_recurrentes(company)
        total += len(resultat['generees'])
    return total
