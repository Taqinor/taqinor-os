"""WIR5/AUD725 — Tâches Celery beat de la flotte.

* ``generer_echeances_entretien_quotidien`` (WIR5, quotidien) — génération
  réelle des échéances d'entretien flotte (FLOTTE16). Avant cette tâche,
  ``services.generer_echeances_entretien`` n'avait NI entrée Celery beat NI
  déclencheur UI — seule la commande manage fonctionnait
  (``manage.py generer_echeances_entretien``). L'onglet Échéances ET le KPI
  « entretien » du Cockpit Flotte restaient silencieusement vides en
  production. Cette tâche ferme cet écart en balayant chaque société
  opérationnelle et en matérialisant les échéances dues (idempotent — aucun
  doublon d'échéance ouverte par plan).
* ``generer_couts_contrat_mensuel`` (AUD725, mensuel) — même écart pour le
  coût récurrent des contrats véhicule (leasing/LLD/location) : réutilise
  ``services.generer_couts_contrat``, idempotent (aucun doublon de coût par
  contrat/période).

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.sav.tasks``/``apps.rh.tasks``.

Multi-tenant : boucle par société opérationnelle (``active_companies()``,
SCA19) ; une société qui échoue n'empêche jamais les suivantes
(best-effort, journalisé).
"""
import datetime
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


@shared_task(name='flotte.generer_couts_contrat_mensuel')
def generer_couts_contrat_mensuel():
    """AUD725 — Beat Celery mensuel : matérialise le coût récurrent DU MOIS
    COURANT de chaque ``ContratVehicule`` (leasing/LLD/location) dans le
    grand livre unifié ``CoutVehicule`` (réutilise EXACTEMENT
    ``services.generer_couts_contrat``, aucune logique dupliquée).

    Avant cette tâche, ``generer_couts_contrat`` n'avait NI entrée Celery
    beat NI déclencheur UI — seule la commande manage
    (``manage.py generer_couts_contrats``) fonctionnait, et écrivait de
    surcroît dans un modèle jamais exposé (voir AUD725/``services.py``). Le
    coût du leasing/location n'atteignait donc jamais le Cockpit Flotte ni le
    ledger/TCO, ni automatiquement ni manuellement.

    Multi-tenant : boucle par société opérationnelle (``active_companies()``,
    SCA19) ; une société qui échoue n'empêche jamais les suivantes
    (best-effort, journalisé)."""
    from authentication.selectors import active_companies

    from .services import generer_couts_contrat

    period = datetime.date.today().strftime('%Y-%m')
    total_societes = 0
    total_creees = 0

    for company in active_companies():
        try:
            resultat = generer_couts_contrat(company, period)
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'flotte.generer_couts_contrat_mensuel: échec société %s',
                company.pk, exc_info=True)
            continue
        total_societes += 1
        total_creees += resultat['nb_creees']

    logger.info(
        'flotte.generer_couts_contrat_mensuel: %s société(s) traitée(s), '
        '%s coût(s) de contrat créé(s)', total_societes, total_creees)
    return {'societes': total_societes, 'couts_crees': total_creees}
