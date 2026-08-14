"""Récepteurs d'événements métier (M6) du module fidélité — NTRET9.

S'abonne à ``core.events.vente_validee`` — un signal POSÉ par ce lot mais PAS
ENCORE ÉMIS par ``apps.pos``/``apps.ventes`` : émettre depuis une app métier
qui n'appartient pas à ce lot (lane SUPPLY = ``fidelite``/``ecommerce_connect``
uniquement) est hors périmètre. L'abonné ci-dessous est prêt et TESTÉ (les
tests envoient le signal directement) ; le branchement de l'émission réelle
côté ``pos``/``ventes`` est un lot séparé, propriétaire de ces apps.
"""
import logging

from django.dispatch import receiver

from core.events import vente_validee

logger = logging.getLogger(__name__)


@receiver(vente_validee, dispatch_uid='fidelite_crediter_points_sur_vente_validee')
def _crediter_points_sur_vente_validee(sender, company, client, montant_ttc,
                                       source_type, source_id=None, user=None,
                                       **kwargs):
    """À chaque vente validée, crédite les points de fidélité (best-effort).

    Ne laisse JAMAIS une exception remonter à l'émetteur : une vente ne doit
    jamais échouer à cause de la fidélité (NTRET9)."""
    from .services import crediter_points_pour_vente

    try:
        crediter_points_pour_vente(
            company=company, client=client, montant_ttc=montant_ttc,
            source_type=source_type, source_id=source_id, user=user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (NTRET9)
        logger.exception(
            'fidelite: échec crédit points pour vente %s/%s (best-effort, '
            'ignoré)', source_type, source_id)
