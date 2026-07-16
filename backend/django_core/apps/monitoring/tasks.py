"""YSERV3 — Beat Celery quotidien : balayage monitoring (synchro fournisseur +
évaluation de sous-performance) pour chaque système supervisé.

Avant cette tâche, ``monitoring.services.sync_system`` et
``evaluate_underperformance`` n'étaient appelés QUE depuis les actions de vue
(``monitoring/views.py`` — ``sync-now`` et la saisie manuelle) — vérifié :
aucun beat, aucune tâche périodique. Résultat : la détection de
sous-performance et l'auto-ticket ne se déclenchaient que si un humain ouvrait
l'écran monitoring d'un chantier. Cette tâche ferme cet écart : chaque système
supervisé (``MonitoringConfig`` à fournisseur actif) est synchronisé puis
évalué chaque nuit, sans action humaine — réutilise EXACTEMENT
``services.sync_system``/``services.evaluate_underperformance`` (aucune
logique dupliquée).

No-op propre quand le fournisseur est le NoOp (``sync_system``/
``evaluate_underperformance`` sont déjà no-op sûrs dans ce cas — comportement
actuel inchangé, juste appelé automatiquement).

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.sav.tasks``/``apps.rh.tasks``.

Multi-tenant : boucle par société, puis par ``MonitoringConfig`` de cette
société ; une société ou un système qui échoue n'empêche jamais les suivants
(best-effort, journalisé).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='monitoring.balayage_quotidien')
def balayage_quotidien():
    """YSERV3 — Pour chaque société, pour chaque ``MonitoringConfig`` à
    fournisseur actif : synchronise les relevés (``sync_system``) puis évalue
    la sous-performance (``evaluate_underperformance``). Best-effort par
    système : une exception sur un système n'empêche jamais les suivants.
    Provider NoOp (ou config désactivée) → ``sync_system`` importe 0 relevé,
    aucun crash, comportement inchangé.
    """
    from authentication.selectors import active_companies

    from .models import MonitoringConfig
    from .services import evaluate_underperformance, sync_system

    total_systemes = 0
    total_importes = 0
    total_sous_performants = 0

    # SCA19 — source unique : un tenant suspendu n'est plus balayé.
    for company in active_companies():
        configs = (MonitoringConfig.objects
                   .filter(company=company)
                   .select_related('installation'))
        for config in configs:
            installation = config.installation
            try:
                imported, _provider = sync_system(installation)
                total_importes += imported
                result = evaluate_underperformance(installation)
                if result.get('underperforming'):
                    total_sous_performants += 1
            except Exception:  # pragma: no cover - défensif, isolation système
                logger.warning(
                    'monitoring.balayage_quotidien: échec système %s '
                    '(société %s)', installation.pk, company.pk,
                    exc_info=True)
                continue
            total_systemes += 1

    logger.info(
        'monitoring.balayage_quotidien: %s système(s) traité(s), %s '
        'relevé(s) importé(s), %s sous-performant(s)',
        total_systemes, total_importes, total_sous_performants)
    return {
        'systemes': total_systemes,
        'releves_importes': total_importes,
        'sous_performants': total_sous_performants,
    }
