"""Récepteurs d'événements onboarding (NTDMO12).

Auto-coche les items de checklist « Premiers pas » en réagissant aux ÉVÉNEMENTS
du bus métier (``core.events``) — jamais par polling, et JAMAIS par un import
direct des modèles ventes/crm/stock (même patron que ``crm`` consommant
``devis_accepted``). Câblé au démarrage par ``OnboardingConfig.ready``.

Mappage événement → clé d'auto-complétion (``OnboardingChecklistItem.event_key``) :

* ``devis_sent`` / ``devis_accepted`` → ``'devis'`` (item « Créer votre 1er
  devis »). Le bus n'expose pas d'événement « devis créé » ; l'envoi/
  l'acceptation est le premier jalon de cycle de vie observable — dès qu'un
  devis existe et bouge, l'item se coche pour l'utilisateur agissant.
* ``facture_payee`` → ``'paiement'`` (item « Encaisser votre 1er paiement »).

Les instances (``devis``/``facture``) ne sont manipulées qu'au travers des
kwargs du signal (attributs ``company``/``created_by``) — aucun import de modèle
d'une autre app.
"""
import logging

from django.dispatch import receiver

from core.events import devis_accepted, devis_sent, facture_payee

from .services import completer_par_evenement

logger = logging.getLogger(__name__)


def _safe_complete(event_key, company, user):
    """Best-effort : une erreur ici ne doit jamais casser l'action métier
    (l'émission du signal est déjà actée côté app émettrice)."""
    try:
        completer_par_evenement(event_key, company, user)
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning('NTDMO12 : auto-complétion onboarding échouée pour '
                       'event_key=%s', event_key, exc_info=True)


@receiver(devis_sent, dispatch_uid='onboarding_complete_devis_on_sent')
def _complete_on_devis_sent(sender, devis, user, ancien_statut, **kwargs):
    _safe_complete('devis', getattr(devis, 'company', None), user)


@receiver(devis_accepted, dispatch_uid='onboarding_complete_devis_on_accepted')
def _complete_on_devis_accepted(sender, devis, user, ancien_statut, **kwargs):
    _safe_complete('devis', getattr(devis, 'company', None), user)


@receiver(facture_payee, dispatch_uid='onboarding_complete_paiement_on_payee')
def _complete_on_facture_payee(sender, instance, company, **kwargs):
    # ``facture_payee`` ne porte pas d'utilisateur : on attribue au créateur de
    # la facture (best-effort).
    user = getattr(instance, 'created_by', None)
    _safe_complete('paiement', company, user)
