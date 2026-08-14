"""Tâches Celery de l'app `mrp` (Groupe NTMFG). Autodécouvert par
`erp_agentique.celery` (`autodiscover_tasks()`), comme `apps.ged.tasks`/
`apps.stock.tasks`. Toute la logique métier vit dans `services`/`selectors`
(testable sans Celery) ; ces tâches ne sont que de fines enveloppes
planifiables — un déploiement SANS Celery beat n'exécute simplement jamais
ces tâches (dégradation propre, pas d'exception).

Boucle PAR société active (jamais une company lue d'une requête — pattern
`authentication.selectors.active_companies`, SCA19 : exclut les tenants
suspendus) ; une exception sur l'une n'empêche jamais les suivantes
(best-effort, journalisé).
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── NTMFG30 — Recalcul MRP nocturne + notification des ruptures prévisionnelles ─

def _deja_notifie_recemment(event_type, link, *, today=None):
    """Vrai si une notification portant CE lien a déjà été créée AUJOURD'HUI
    OU LA VEILLE (Africa/Casablanca) — évite de re-notifier chaque nuit une
    rupture déjà signalée récemment pour le même produit tant qu'elle n'a
    pas disparu du calcul MRP au moins un jour. Quel que soit le
    destinataire (idempotence PAR société+produit, pas par destinataire)."""
    from apps.notifications.models import Notification

    today = today or timezone.localdate()
    hier = today - timezone.timedelta(days=1)
    try:
        return Notification.objects.filter(
            event_type=event_type, link=link,
            created_at__date__gte=hier, created_at__date__lte=today,
        ).exists()
    except Exception:  # pragma: no cover - défensif
        return False


@shared_task(name='mrp.recalculer_besoins_nocturne')
def recalculer_besoins_nocturne():
    """NTMFG30 — pour CHAQUE société active, exécute le calcul de besoins nets
    (NTMFG5, `selectors.calculer_besoins_nets`) sur l'horizon
    `ParametresMRP.horizon_mrp_jours` (NTMFG29) et notifie best-effort
    (`notifications.notify_many`, réutilise `EventType.STOCK_LOW`, même
    famille que l'alerte réappro existante `stock.recompute_reordering`) les
    responsables achats/production si une rupture prévisionnelle
    (``besoin_net`` != 0) apparaît. Idempotent : au plus une notification par
    société+produit sur une fenêtre glissante de 2 jours (jamais de doublon
    si déjà notifiée hier pour le même produit). Renvoie
    ``{company_id: nb_ruptures_notifiees}``."""
    from authentication.selectors import active_companies

    from .selectors import calculer_besoins_nets
    from .services import parametres_mrp

    today = timezone.localdate()
    result = {}
    for company in active_companies():  # SCA19 — exclut les tenants suspendus
        try:
            parametres = parametres_mrp(company)
            lignes = calculer_besoins_nets(
                company,
                stock_securite_pct=parametres.stock_securite_pct_defaut,
                horizon_jours=parametres.horizon_mrp_jours)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête pas
            logger.warning(
                'mrp.recalculer_besoins_nocturne: échec calcul société %s',
                company.pk, exc_info=True)
            continue

        ruptures = [ligne for ligne in lignes if ligne.get('besoin_net') not in (None, '0')]
        if not ruptures:
            result[company.id] = 0
            continue

        notifiees = 0
        for ligne in ruptures:
            link = f'mrp-rupture-{company.id}-{ligne["produit_id"]}'
            if _deja_notifie_recemment('stock_low', link, today=today):
                continue
            try:
                from apps.notifications.models import EventType
                from apps.notifications.services import notify_many, resolve_recipients

                recipients = resolve_recipients(company, EventType.STOCK_LOW)
                notify_many(
                    recipients, EventType.STOCK_LOW,
                    title=f'Rupture prévisionnelle — {ligne["produit_nom"]}',
                    body=(f'Besoin net {ligne["besoin_net"]} '
                          f'({ligne.get("proposition") or "à couvrir"}) '
                          f'dans l\'horizon MRP.'),
                    link=link, company=company)
                notifiees += 1
            except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
                logger.warning(
                    'mrp.recalculer_besoins_nocturne: notification échouée '
                    'société %s produit %s', company.pk, ligne['produit_id'],
                    exc_info=True)
        result[company.id] = notifiees
    return result


# ── NTMFG31 — Purge/archivage des OF prototype anciens ───────────────────

@shared_task(name='mrp.archiver_of_prototype_anciens')
def archiver_of_prototype_anciens_task():
    """NTMFG31 — pour CHAQUE société active, archive (soft-delete) les OF
    prototype clôturés depuis plus de `ParametresMRP.retention_prototype_jours`
    (NTMFG29, `services.archiver_of_prototype_anciens`) — jamais les OF de
    production normale. Idempotent (double exécution sans effet
    supplémentaire — les OF déjà archivés sortent du queryset). Renvoie
    ``{company_id: nb_of_archives}``."""
    from authentication.selectors import active_companies

    from .services import archiver_of_prototype_anciens

    result = {}
    for company in active_companies():  # SCA19 — exclut les tenants suspendus
        try:
            archives = archiver_of_prototype_anciens(company)
            result[company.id] = len(archives)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête pas
            logger.warning(
                'mrp.archiver_of_prototype_anciens: échec société %s',
                company.pk, exc_info=True)
    return result
