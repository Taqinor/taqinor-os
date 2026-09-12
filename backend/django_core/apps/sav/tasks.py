"""YSERV5 — Beat Celery quotidien : génération automatique des visites
préventives dues (opt-in par société).

Avant cette tâche, ``apps/sav/maintenance.py generer_visites_dues()``
n'était appelée QUE par le bouton manuel (action ``generer-dus``) — aucun job
beat (vérifié ``erp_agentique/celery.py``). Le sweep FG1 ne fait que
NOTIFIER, jamais matérialiser. Cette tâche ferme cet écart : les sociétés qui
activent ``SavSlaSettings.generation_auto_visites`` voient leurs visites
dues (sous ``visites_avance_jours`` jours) créées chaque nuit sans action
humaine — réutilise EXACTEMENT ``maintenance.generer_visites_dues`` (aucune
logique dupliquée), étendue pour accepter un horizon d'avance.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.rh.tasks``/``apps.contrats.scheduled``.

Multi-tenant : boucle par société active, OFF par défaut = no-op total. Une
société qui échoue n'empêche jamais les suivantes (best-effort, journalisé).
"""
import logging
from contextlib import contextmanager

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

_EVENT_TYPE = 'sav_visites_auto_generees'

# ── NTSRV38 — verrou d'exclusion des balayages SLA ──────────────────────────
# Les deux balayages SLA tournent au quart d'heure (beat). Une exécution qui
# déborde (beat qui retire, worker relancé, exécution manuelle en parallèle)
# ne doit JAMAIS notifier deux fois le même palier du même ticket : c'est une
# course entre deux lectures de `Ticket.sla_escalade_paliers_notifies` avant
# que l'une n'écrive. Le verrou la ferme.
#
# C'est un VERROU (posé puis RELÂCHÉ), pas une clé d'idempotence à durée fixe
# (`core.idempotent_task`) : un appel SÉQUENTIEL suivant doit pouvoir tourner
# normalement — seul un appel CONCURRENT est court-circuité. Le TTL n'est
# qu'un filet si le processus meurt en cours de balayage.
_VERROU_TTL = 600  # secondes


@contextmanager
def _verrou_scan(nom):
    """Verrou best-effort nommé. Cède ``True`` si CET appel l'a obtenu.

    Cache indisponible (Redis coupé) → on cède ``True`` sans verrou : un
    balayage SLA qui ne tourne plus du tout serait pire que le risque de
    double notification, déjà atténué par l'idempotence sur le ticket.
    """
    cle = f'sav-sla-scan:{nom}'
    try:
        obtenu = bool(cache.add(cle, 1, _VERROU_TTL))
    except Exception:  # pragma: no cover - cache KO → on n'empêche pas le scan
        logger.warning('sav: verrou %s indisponible (cache KO)', nom)
        yield True
        return
    try:
        yield obtenu
    finally:
        if obtenu:
            try:
                cache.delete(cle)
            except Exception:  # pragma: no cover - défensif
                logger.warning('sav: libération du verrou %s KO', nom)


def _responsables(company):
    """Responsables/admins actifs de la société (destinataires de la
    notification). Repli sur tous les actifs si aucun palier trouvé — même
    logique que ``apps.rh.tasks._recipients``."""
    try:
        from authentication.models import CustomUser
        base = list(CustomUser.objects.filter(company=company, is_active=True))
    except Exception:  # pragma: no cover - défensif
        return []
    managers = [
        u for u in base
        if getattr(u, 'is_admin_role', False)
        or getattr(u, 'role_tier', None) in ('admin', 'responsable')
    ]
    return managers or base


@shared_task(name='sav.generer_visites_dues_quotidien')
def generer_visites_dues_quotidien():
    """YSERV5 — Pour chaque société ayant activé
    ``SavSlaSettings.generation_auto_visites`` : matérialise les visites
    préventives dues sous ``visites_avance_jours`` jours (idempotence déjà
    garantie par ``generer_visites_dues``), puis notifie les responsables
    quand au moins un ticket a été créé. OFF (défaut) = société totalement
    ignorée — aucun effet."""
    from authentication.models import CustomUser
    from authentication.selectors import active_companies

    from apps.notifications.services import notify
    from .maintenance import generer_visites_dues
    from .models import SavSlaSettings

    total_societes = 0
    total_generes = 0

    # SCA19 — restreint aux sociétés opérationnelles via la source unique : un
    # tenant suspendu/en fermeture n'a plus de génération de visites préventives.
    for reglage in SavSlaSettings.objects.filter(
            generation_auto_visites=True, company__isnull=False,
            company__in=active_companies()).select_related('company'):
        company = reglage.company
        try:
            acteur = (
                CustomUser.objects.filter(
                    company=company, is_active=True)
                .order_by('-is_superuser', 'id').first())
            n = generer_visites_dues(
                company, acteur, avance_jours=reglage.visites_avance_jours)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'sav.generer_visites_dues_quotidien: échec société %s',
                company.pk, exc_info=True)
            continue
        total_societes += 1
        if not n:
            continue
        total_generes += n
        titre = f'{n} visite(s) préventive(s) générée(s) automatiquement'
        corps = (
            f'{n} ticket(s) SAV préventif(s) ont été créés automatiquement '
            f'(avance {reglage.visites_avance_jours} j).')
        for user in _responsables(company):
            try:
                notify(
                    user, _EVENT_TYPE, titre, body=corps,
                    link='/sav/contrats-maintenance', company=company)
            except Exception:  # pragma: no cover - défensif
                logger.warning(
                    'sav.generer_visites_dues_quotidien: notification '
                    'échouée vers %s', user, exc_info=True)

    logger.info(
        'sav.generer_visites_dues_quotidien: %s société(s) traitée(s), %s '
        'visite(s) générée(s)', total_societes, total_generes)
    return {'societes': total_societes, 'visites_generees': total_generes}


# ── WIR30 — Beat pour XSAV6 (pré-alerte SLA + escalade) ─────────────────────

@shared_task(name='sav.scan_sla_pre_alerts_and_escalations_quotidien')
def scan_sla_pre_alerts_and_escalations_quotidien():
    """WIR30 — Planifie ``apps.sav.views.scan_sla_pre_alerts_and_escalations``
    (XSAV6), bâtie et testée (``tests_xsav6.py``) mais jamais ajoutée au beat
    jusqu'ici. DISTINCT de ``scan_sla_breaches`` (planifiée séparément par
    NTSRV38, ne pas dupliquer ici). OFF par défaut par société
    (``sla_warning_days=0``, ``escalade_activee=False``) : aucun effet tant
    qu'une société n'active pas explicitement l'un des deux réglages.

    NTSRV38 — c'est ICI que vivent les PALIERS d'escalade multi-niveaux
    (NTSRV12, ``_notifier_paliers``), donc c'est cette tâche que le beat
    rappelle toutes les 15 minutes (le nom ``…_quotidien`` est hérité de
    WIR30 et conservé : il est référencé par ``beat_schedule`` et
    ``CELERY_TASK_ROUTES``). Deux exécutions CONCURRENTES sont exclues par le
    verrou ; une exécution séquentielle suivante tourne normalement."""
    with _verrou_scan('pre-alerts') as obtenu:
        if not obtenu:
            logger.info(
                'sav.scan_sla_pre_alerts_and_escalations: exécution '
                'concurrente ignorée (verrou tenu)')
            return {'skipped': True}
        from apps.sav.views import scan_sla_pre_alerts_and_escalations
        return scan_sla_pre_alerts_and_escalations()


# ── NTSRV38 — Beat au quart d'heure pour FG81 (violation SLA) ───────────────

@shared_task(name='sav.scan_sla_breaches_quart_heure')
def scan_sla_breaches_quart_heure():
    """NTSRV38 — Planifie ``apps.sav.views.scan_sla_breaches`` (FG81), qui
    n'avait AUCUNE entrée beat : elle ne tournait qu'à la demande (commande
    de gestion / appel manuel), donc un dépassement de SLA n'était notifié
    que si quelqu'un lançait le balayage.

    Cadence : toutes les 15 minutes, sous le MÊME type de verrou que la
    tâche de pré-alerte/escalade — deux exécutions simultanées n'écrivent
    jamais deux fois ``sla_breach`` ni n'émettent deux notifications pour le
    même ticket. OFF par société tant que ``sla_breach_enabled`` est False
    (défaut) : le balayage ne modifie alors rien."""
    with _verrou_scan('breaches') as obtenu:
        if not obtenu:
            logger.info('sav.scan_sla_breaches: exécution concurrente '
                        'ignorée (verrou tenu)')
            return {'skipped': True}
        from apps.sav.views import scan_sla_breaches
        return {'skipped': False, 'tickets': scan_sla_breaches()}
