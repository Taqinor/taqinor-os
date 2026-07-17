"""NTEDU22 — Beat Celery hebdomadaire de l'app ``education`` : matérialise
les séances de la semaine à venir depuis l'emploi du temps actif.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.rh.tasks``/``apps.sante.tasks``. Multi-tenant : boucle par société
(``authentication.Company``), jamais une lecture de company depuis un corps
de requête ; une exception sur l'une n'empêche jamais les suivantes
(best-effort, journalisé)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='education.generer_seances_semaine')
def generer_seances_semaine_task():
    """NTEDU22 — génère, pour CHAQUE société, les séances de la semaine à
    venir à partir des créneaux d'emploi du temps actifs. Best-effort par
    société : une société en échec n'empêche jamais les suivantes."""
    from authentication.models import Company

    from .services_planning import generer_seances_semaine

    total = 0
    for company in Company.objects.all():
        try:
            creees = generer_seances_semaine(company)
            total += len(creees)
        except Exception:  # noqa: BLE001 - défensif, best-effort
            logger.exception(
                'education.generer_seances_semaine: échec société %s',
                company.id)
    return total
