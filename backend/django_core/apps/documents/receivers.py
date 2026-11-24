"""Récepteurs d'événements du dossier contractuel (conception § 5).

Câblé au démarrage par ``DocumentsConfig.ready``. Aucun import d'une autre
app métier au chargement : le chantier d'un devis est lu par
``apps.installations.selectors`` au moment de l'événement.

- ``devis_accepted`` → APRÈS le commit de l'acceptation
  (``transaction.on_commit``), les cinq brouillons du chantier du devis sont
  préparés. Jamais dans la transaction de signature, jamais bloquant : une
  erreur est journalisée et n'annule rien (une vraie signature ne tombe
  jamais pour un contrat).
- ``devis_acceptation_annulee`` et ``chantier_annule`` → les actes non signés
  passent « annulé » (best-effort, point de sauvegarde) ; une ré-acceptation
  les rétablit (``preparer_dossier``).
"""
import logging

from django.db import transaction
from django.dispatch import receiver

from core.events import (
    abonne_best_effort, chantier_annule, devis_acceptation_annulee,
    devis_accepted,
)

logger = logging.getLogger(__name__)

MOTIF_DESACCEPTATION = "Acceptation du devis annulée"
MOTIF_CHANTIER_ANNULE = 'Chantier annulé'


def _chantier_du_devis(devis):
    from apps.installations.selectors import installation_for_devis
    company = getattr(devis, 'company', None)
    if company is None or getattr(devis, 'pk', None) is None:
        return None
    return installation_for_devis(devis, company=company)


def preparer_dossier_du_devis(devis, user=None):
    """Prépare le dossier du chantier de ``devis`` (s'il existe). Ne lève
    jamais : une erreur est journalisée."""
    try:
        chantier = _chantier_du_devis(devis)
        if chantier is None or chantier.annule:
            return None
        from .contrats.services import preparer_dossier
        return preparer_dossier(chantier, user)
    except Exception:  # noqa: BLE001 — jamais bloquant pour la vente
        logger.exception('contrats : préparation du dossier impossible '
                         '(devis %s)', getattr(devis, 'pk', None))
        return None


@receiver(devis_accepted,
          dispatch_uid='documents_preparer_dossier_on_devis_accepted')
def _preparer_dossier_on_devis_accepted(sender, devis, user=None, **kwargs):
    """Après le commit de l'acceptation : le chantier existe (créé par
    ``installations`` dans la même transaction), ses actes sont préparés."""
    try:
        transaction.on_commit(
            lambda: preparer_dossier_du_devis(devis, user))
    except Exception:  # noqa: BLE001 — jamais bloquant pour la vente
        logger.exception('contrats : préparation différée impossible '
                         '(devis %s)', getattr(devis, 'pk', None))


@receiver(devis_acceptation_annulee,
          dispatch_uid='documents_annuler_dossier_on_acceptation_annulee')
@abonne_best_effort
def _annuler_dossier_on_acceptation_annulee(sender, devis, user=None,
                                            **kwargs):
    chantier = _chantier_du_devis(devis)
    if chantier is None:
        return
    from .contrats.services import annuler_dossier
    annuler_dossier(chantier, MOTIF_DESACCEPTATION)


@receiver(chantier_annule, dispatch_uid='documents_annuler_dossier_on_chantier_annule')
@abonne_best_effort
def _annuler_dossier_on_chantier_annule(sender, installation, user=None,
                                        **kwargs):
    if installation is None:
        return
    from .contrats.services import annuler_dossier
    annuler_dossier(installation, getattr(installation, 'motif_annulation', '')
                    or MOTIF_CHANTIER_ANNULE)
