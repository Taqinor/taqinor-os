"""WIR148 — Tâches Celery du module Immobilier.

Autodécouvert par `erp_agentique.celery` (`autodiscover_tasks()`), comme
`apps.ged.tasks`. Toute la logique métier vit dans `services`
(`generer_echeancier`, déjà testée sans Celery — NTPRO6/`test_ntpro6_
echeancier.py`) ; cette tâche n'est qu'une fine enveloppe planifiable, même
patron que la commande manage `generer_echeances_loyer` mais SANS écriture
console et avec l'isolement par société des autres tâches beat du dépôt
(`ged.migrer_pieces_jointes`, `contrats.generer_factures_recurrentes_dues`…).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='immobilier.generer_echeances_loyer')
def generer_echeances_loyer_task():
    """WIR148 — Génère l'échéancier de loyer des baux ACTIFS, quotidien.

    IDEMPOTENT (unique_together bail + periode_debut dans
    `services.generer_echeancier`) : rejouer ne duplique jamais une échéance
    déjà générée. Une société KO n'interrompt jamais les suivantes."""
    from authentication.selectors import active_companies

    from apps.immobilier.models import Bail
    from apps.immobilier.services import generer_echeancier

    total_baux = 0
    total_creees = 0
    for company in active_companies():  # SCA19 — exclut les tenants suspendus
        try:
            baux = Bail.objects.filter(
                company=company, statut=Bail.Statut.ACTIF)
            for bail in baux:
                total_baux += 1
                total_creees += len(generer_echeancier(bail))
        except Exception:  # pragma: no cover - défensif, une société KO
            # n'interrompt jamais les suivantes.
            logger.warning(
                'immobilier.generer_echeances_loyer: échec société %s',
                company.pk, exc_info=True)
    logger.info(
        'immobilier.generer_echeances_loyer: %d bail(aux) actif(s), '
        '%d échéance(s) créée(s)',
        total_baux, total_creees)
    return {'baux': total_baux, 'echeances_creees': total_creees}
