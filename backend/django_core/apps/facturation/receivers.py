"""Abonnés du bus d'événements (M6) du module Facturation.

AMET4 (D-SIGN-AUTO = a, D-AMET4-PROVISOIRE) — la facture d'ACOMPTE naît en
BROUILLON PROVISOIRE à l'acceptation d'un devis, depuis l'échéancier figé
(AMET2), et tombe avec la dés-acceptation tant qu'elle est brouillon. Les
deux corps vivent dans ``apps.ventes.domain.facturation_vente`` (propriétaire
facturation) : ce module ne fait que s'abonner (enregistré par
``FacturationConfig.ready``).
"""
from django.dispatch import receiver

from core import dsr
from core.events import devis_accepted, devis_acceptation_annulee


def _garde_identite_acheteur(company, subject_identifier):
    """ASUP3 (C-ASUP-001) — garde d'effacement : une facture non brouillon
    sans instantané d'acheteur bloque l'effacement de la personne (409)."""
    from apps.ventes.domain.instantanes_facture import (
        garde_pieces_legales_sans_identite_figee)
    return garde_pieces_legales_sans_identite_figee(company, subject_identifier)


dsr.register_erasure_guard('pieces_legales_sans_identite_figee',
                           _garde_identite_acheteur)


@receiver(devis_accepted,
          dispatch_uid='facturation_acompte_provisoire_on_devis_accepted')
def _acompte_provisoire_on_devis_accepted(sender, devis, user=None,
                                          canal='', **kwargs):
    """Émis DANS la transaction de l'acceptation (rollback ⇒ aucun brouillon).
    Un avenant négocié (VNT59) ne crée rien : son aval est rattaché en
    strict. Idempotent (tranche d'acompte déjà couverte ⇒ rien)."""
    if canal == 'avenant_negocie':
        return
    from apps.ventes.domain.facturation_vente import acompte_a_l_acceptation
    acompte_a_l_acceptation(devis, user)


@receiver(devis_acceptation_annulee,
          dispatch_uid='facturation_retirer_acompte_on_acceptation_annulee')
def _retirer_acompte_on_acceptation_annulee(sender, devis, user=None,
                                            **kwargs):
    """Annule le brouillon d'acompte PROVISOIRE (jamais supprimé, aucun
    avoir) ; un acompte émis bloque la dés-acceptation en amont (409)."""
    from apps.ventes.domain.facturation_vente import (
        retirer_acompte_automatique)
    retirer_acompte_automatique(devis, user=user)
