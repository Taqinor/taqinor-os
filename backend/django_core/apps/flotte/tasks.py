"""WIR5 — Beat Celery quotidien : génération réelle des échéances d'entretien
flotte (FLOTTE16).

Avant cette tâche, ``services.generer_echeances_entretien`` n'avait NI entrée
Celery beat NI déclencheur UI — seule la commande manage fonctionnait
(``manage.py generer_echeances_entretien``). L'onglet Échéances ET le KPI
« entretien » du Cockpit Flotte restaient silencieusement vides en
production. Cette tâche ferme cet écart en balayant chaque société
opérationnelle et en matérialisant les échéances dues (idempotent — aucun
doublon d'échéance ouverte par plan).

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.sav.tasks``/``apps.rh.tasks``.

Multi-tenant : boucle par société opérationnelle (``active_companies()``,
SCA19) ; une société qui échoue n'empêche jamais les suivantes
(best-effort, journalisé).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='flotte.generer_echeances_entretien_quotidien')
def generer_echeances_entretien_quotidien():
    """FLOTTE16 — Pour chaque société opérationnelle : génère les échéances
    d'entretien dues depuis les plans actifs (réutilise EXACTEMENT
    ``services.generer_echeances_entretien``, aucune logique dupliquée) et
    diffuse les alertes best-effort associées."""
    from authentication.selectors import active_companies

    from .services import generer_echeances_entretien

    total_societes = 0
    total_creees = 0

    for company in active_companies():
        try:
            resultat = generer_echeances_entretien(company, alerter=True)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'flotte.generer_echeances_entretien_quotidien: échec '
                'société %s', company.pk, exc_info=True)
            continue
        total_societes += 1
        total_creees += resultat['nb_creees']

    logger.info(
        'flotte.generer_echeances_entretien_quotidien: %s société(s) '
        'traitée(s), %s échéance(s) créée(s)', total_societes, total_creees)
    return {'societes': total_societes, 'echeances_creees': total_creees}
