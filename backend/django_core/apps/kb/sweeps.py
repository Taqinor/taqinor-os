"""Balayages quotidiens (Celery Beat) de la Base de connaissances.

Calqué sur le pattern ``apps/notifications/sweeps.py`` (FG1) : IDEMPOTENT (ne
mute aucune donnée métier, ré-exécuter ne fait que ré-émettre des
notifications), MULTI-TENANT (chaque société traitée isolément), DÉFENSIF
(chaque société est dans son propre try/except — une société en erreur
n'empêche pas les suivantes, aucune exception ne remonte).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _companies():
    """Toutes les sociétés actives. Vide si erreur."""
    try:
        from authentication.models import Company
        return list(Company.objects.filter(actif=True))
    except Exception:  # pragma: no cover
        logger.warning('kb sweeps: chargement des sociétés impossible',
                       exc_info=True)
        return []


@shared_task(name='kb.sweep_lectures_obligatoires')
def sweep_lectures_obligatoires():
    """XKB7 — Relance quotidienne des non-lecteurs de lecture obligatoire.

    Best-effort par société : une société en erreur n'empêche pas les
    suivantes. Renvoie le total de relances émises.
    """
    from . import services

    total = 0
    for company in _companies():
        try:
            total += services.relancer_lectures_obligatoires(company=company)
        except Exception:  # pragma: no cover
            logger.warning(
                'kb sweeps: société %s échouée globalement',
                getattr(company, 'pk', None), exc_info=True)
    logger.info(
        'sweep_lectures_obligatoires: %s relance(s) émise(s)', total)
    return total
