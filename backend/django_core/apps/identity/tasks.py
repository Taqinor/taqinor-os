"""Tâches Celery de l'app identity — autodécouvertes par `erp_agentique.celery`
(`app.autodiscover_tasks()`), aucun enregistrement manuel requis.

WIR50 — enveloppe planifiable du nettoyage break-glass (NTSEC22). Sans elle, un
octroi d'accès d'urgence ÉCHU conserve le rôle Administrateur tant qu'il n'est
pas révoqué à la main (élévation de privilège persistante) : la révocation doit
tourner périodiquement (toutes les ~10 min).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='identity.revoke_expired_break_glass')
def revoke_expired_break_glass_task():
    """NTSEC22 — révoque les accès break-glass échus (toutes sociétés).

    Enveloppe fine : délègue au service ``breakglass.revoke_expired`` qui balaie
    TOUS les octrois échus non révoqués (``company=None`` = balayage global,
    idempotent) et restaure le rôle antérieur."""
    from apps.identity.breakglass import revoke_expired
    n = revoke_expired()
    logger.info('identity.revoke_expired_break_glass: %d accès révoqués.', n)
    return {'revoques': n}
