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
* WIR59 — ``intervention_completed`` → ``'chantier'`` (item « Suivre votre
  1er chantier ») : une intervention terminée/validée (``apps.installations``,
  YSERV2) est le premier jalon observable de suivi de chantier — même patron
  que devis/paiement, aucun import d'``apps.installations`` ici (le signal
  porte tout ce qu'il faut dans ses kwargs).

Les instances (``devis``/``facture``/``intervention``) ne sont manipulées qu'au
travers des kwargs du signal (attributs ``company``/``created_by``/``user``) —
aucun import de modèle d'une autre app.
"""
from django.dispatch import receiver

from core.events import (
    abonne_best_effort, devis_accepted, devis_sent, facture_payee,
    intervention_completed,
)

from .services import completer_par_evenement


# APAR48 — chaque abonné est ANNEXE : ``@abonne_best_effort`` (core.events)
# l'isole dans son point de sauvegarde et journalise son erreur — il ne casse
# jamais l'action métier émettrice (signature, encaissement, synchro terrain).
# Remplace le filet maison d'ADEV54 (même effet, une seule définition).


@receiver(devis_sent, dispatch_uid='onboarding_complete_devis_on_sent')
@abonne_best_effort
def _complete_on_devis_sent(sender, devis, user, ancien_statut, **kwargs):
    completer_par_evenement('devis', getattr(devis, 'company', None), user)


@receiver(devis_accepted, dispatch_uid='onboarding_complete_devis_on_accepted')
@abonne_best_effort
def _complete_on_devis_accepted(sender, devis, user, ancien_statut, **kwargs):
    completer_par_evenement('devis', getattr(devis, 'company', None), user)


@receiver(facture_payee, dispatch_uid='onboarding_complete_paiement_on_payee')
@abonne_best_effort
def _complete_on_facture_payee(sender, instance, company, **kwargs):
    # ``facture_payee`` ne porte pas d'utilisateur : on attribue au créateur de
    # la facture (best-effort).
    user = getattr(instance, 'created_by', None)
    completer_par_evenement('paiement', company, user)


@receiver(intervention_completed,
          dispatch_uid='onboarding_complete_chantier_on_intervention')
@abonne_best_effort
def _complete_on_intervention_completed(
        sender, intervention, company, user, **kwargs):
    # WIR59 — ``user`` peut être None (action système) :
    # ``completer_par_evenement`` est no-op sans utilisateur.
    completer_par_evenement('chantier', company, user)
