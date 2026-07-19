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

from celery import shared_task

logger = logging.getLogger(__name__)

_EVENT_TYPE = 'sav_visites_auto_generees'


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


# ── WIR30 — Beat quotidien pour XSAV6 (pré-alerte SLA + escalade) ───────────

@shared_task(name='sav.scan_sla_pre_alerts_and_escalations_quotidien')
def scan_sla_pre_alerts_and_escalations_quotidien():
    """WIR30 — Planifie ``apps.sav.views.scan_sla_pre_alerts_and_escalations``
    (XSAV6), bâtie et testée (``tests_xsav6.py``) mais jamais ajoutée au beat
    jusqu'ici. DISTINCT de ``scan_sla_breaches`` (planifiée séparément par
    NTSRV38, ne pas dupliquer ici). OFF par défaut par société
    (``sla_warning_days=0``, ``escalade_activee=False``) : aucun effet tant
    qu'une société n'active pas explicitement l'un des deux réglages."""
    from apps.sav.views import scan_sla_pre_alerts_and_escalations
    return scan_sla_pre_alerts_and_escalations()
