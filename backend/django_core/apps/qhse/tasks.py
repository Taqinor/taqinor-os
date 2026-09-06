"""Tâches Celery de l'app QHSE — auto-découvertes par `erp_agentique.celery`
(`app.autodiscover_tasks()`), aucun enregistrement manuel requis.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='qhse.escalader_checkins_en_retard')
def escalader_checkins_en_retard_task():
    """XFSM24 — Enveloppe Celery Beat du service homonyme.

    Délègue entièrement au service (même logique, testable en dehors de
    Celery via un appel direct de fonction).
    """
    from apps.qhse.services import escalader_checkins_en_retard
    escalades = escalader_checkins_en_retard()
    return {'escalades': [c.id for c in escalades]}


@shared_task(name='qhse.relancer_csh_du_jour')
def relancer_csh_du_jour_task():
    """PACT184 (XQHS12) — Enveloppe Celery Beat du service homonyme (rappel
    légal de réunion CSH trimestrielle, Code du travail — ``csh_relance_due``
    n'avait aucun appelant avant cette tâche).
    """
    from apps.qhse.services import relancer_csh_du_jour
    relancees = relancer_csh_du_jour()
    return {'relancees': [c.id for c in relancees]}


# -- AUD524 -- DEUX SERVICES TESTES ET CORRECTS, SANS AUCUN APPELANT ---------
#
# ``relancer_derogations`` (XQHS2) et ``relancer_audits_planifies_en_retard``
# (XQHS10) n'apparaissaient NULLE PART hors de leurs tests et d'une action
# manuelle de vue : ni ici, ni au ``beat_schedule`` (seules DEUX taches qhse y
# figuraient). Une derogation a echeance et un audit planifie en retard
# n'etaient donc JAMAIS relances automatiquement -- le code etait juste, il ne
# tournait simplement pas. Ces taches ajoutent la CADENCE ; elles ne
# remplacent aucun bouton.


@shared_task(name='qhse.relancer_derogations')
def relancer_derogations_task():
    """AUD524 (XQHS2) -- enveloppe Celery Beat du service homonyme.

    Le service exige une societe : on balaie les societes ACTIVES
    (``active_companies``, AUD415/SCA19 -- jamais les tenants suspendus). Une
    societe en echec n'empeche jamais les suivantes."""
    from authentication.selectors import active_companies
    from apps.qhse.services import relancer_derogations

    total = 0
    for company in active_companies():
        try:
            resultat = relancer_derogations(company) or {}
            total += int(resultat.get('notifiees') or 0)
        except Exception:  # pragma: no cover - best-effort par societe
            logger.exception(
                'qhse.relancer_derogations: societe %s echouee',
                getattr(company, 'id', '?'))
    return {'notifiees': total}


@shared_task(name='qhse.relancer_audits_planifies_en_retard')
def relancer_audits_planifies_en_retard_task():
    """AUD524 (XQHS10) -- enveloppe Celery Beat du service homonyme.

    Le service accepte ``company=None`` (toutes societes), mais on balaie
    quand meme les societes ACTIVES une a une : un tenant suspendu ne doit
    plus recevoir d'alerte (AUD415/SCA19)."""
    from authentication.selectors import active_companies
    from apps.qhse.services import relancer_audits_planifies_en_retard

    total = 0
    for company in active_companies():
        try:
            relances = relancer_audits_planifies_en_retard(company) or []
            total += len(relances)
        except Exception:  # pragma: no cover - best-effort par societe
            logger.exception(
                'qhse.relancer_audits_planifies_en_retard: societe %s echouee',
                getattr(company, 'id', '?'))
    return {'relances': total}
