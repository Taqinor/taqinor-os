"""GED25 — Tâches Celery de la GED (purge automatique de la corbeille).

Autodécouvert par `erp_agentique.celery` (`autodiscover_tasks()`), comme
`apps.ventes.tasks`. Toute la logique métier vit dans `services` (testable sans
Celery) ; ces tâches ne sont qu'une fine enveloppe planifiable.

POLITIQUE DE SÛRETÉ (GED25) :
  * DRY-RUN PAR DÉFAUT. La tâche planifiée ne SUPPRIME RIEN tant que
    `settings.GED_PURGE_AUTO_APPLY` n'est pas explicitement vrai. Par défaut
    elle se contente de COMPTER/LOGGER ce qui SERAIT purgé (signal, jamais
    destructif) — exactement l'esprit « dry-run d'abord » du plan.
  * Elle ne purge QUE des documents DÉJÀ en corbeille (GED26) ayant dépassé le
    délai de grâce, et RE-VÉRIFIE les gardes légales (GED23 write-once /
    GED24 legal hold) par document avant tout effacement (jamais une 500).
  * Multi-tenant : chaque société est traitée bornée à ses propres documents.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='ged.purge_corbeille_echue')
def purge_corbeille_echue():
    """GED25 — Purge planifiée de la corbeille échue (DRY-RUN sauf opt-in).

    Délègue à `services.purger_corbeille_toutes_societes`. L'effacement réel
    n'a lieu QUE si `settings.GED_PURGE_AUTO_APPLY` est vrai ; sinon c'est un
    dry-run pur (rien n'est effacé). Idempotent et safe à ré-exécuter. Renvoie
    le dict de synthèse agrégé (sociétés concernées, éligibles, purgés,
    protégés)."""
    from django.conf import settings

    from . import services

    apply = bool(getattr(settings, 'GED_PURGE_AUTO_APPLY', False))
    result = services.purger_corbeille_toutes_societes(apply=apply)
    logger.info(
        'ged.purge_corbeille_echue: dry_run=%s, %d éligible(s), '
        '%d purgé(s), %d protégé(s) (legal/archive)',
        result['dry_run'], result['eligibles'],
        result['purges'], result['proteges'])
    return result
