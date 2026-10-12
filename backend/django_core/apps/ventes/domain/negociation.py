"""Négociation d'une vente signée (Groupe VNT, D-VNT-2) — une vente par lead.

VNT54 — ``garde_vente_unique`` : ``accept_devis`` (les trois portes : vue
interne, lien public, portail) refuse une DEUXIÈME vente en vigueur sur un lead
quand le devis accepté n'appartient pas à la chaîne de RÉVISION de la vente en
vigueur (``superseded_by`` — une variante, sœur du même groupe
``version_parent``, est une autre chaîne). Rien n'est écrit (règle #4) : la
garde lève avant toute bascule de statut, sous le verrou d'``accept_devis``.

Ordre de chargement : ce module importe ``cycle_vie`` (``AcceptError``) ;
``cycle_vie`` ne l'importe qu'à l'APPEL (import fonction-local), jamais au
chargement — aucun cycle.
"""
import logging

from apps.ventes.domain import cycle_vie as _cycle_vie

logger = logging.getLogger("apps.ventes.services")

#: Code machine du 409 (contrats ``proposal_accept.json`` ``codes_409`` et
#: ``devis_prix_negocie.json`` ``erreurs_409``).
CODE_VENTE_ACTIVE_EXISTANTE = 'vente_active_existante'

#: Message NEUTRE pour le client (lien public, portail) — contrat
#: ``proposal_accept.json`` ``reponses_409.vente_active_existante`` : aucune
#: référence interne exposée.
VENTE_ACTIVE_REFUS_CLIENT = (
    "Cette proposition ne peut pas être signée en l'état : contactez votre "
    'conseiller.')


class VenteActiveExistante(_cycle_vie.AcceptError):
    """VNT54 — 409 ``vente_active_existante`` ; ``vente_active`` =
    ``{id, reference}`` de la vente en vigueur (rendu par la vue interne)."""

    def __init__(self, message, vente_active):
        super().__init__(message, conflict=True,
                         code=CODE_VENTE_ACTIVE_EXISTANTE)
        self.vente_active = vente_active


def vente_active_hors_chaine(devis):
    """La vente en vigueur du lead de ``devis`` qui n'est PAS dans sa chaîne
    de révision (``devis`` et les versions qu'il remplace), ou ``None``.
    Lead absent ⇒ ``None`` (aucune règle par lead sans lead)."""
    if not getattr(devis, 'lead_id', None):
        return None
    from apps.ventes.selectors import (
        devis_predecesseurs_revision_ids, devis_signes_en_vigueur)
    chaine = set(devis_predecesseurs_revision_ids(devis)) | {devis.pk}
    return (devis_signes_en_vigueur(devis.company_id,
                                    lead_ids=[devis.lead_id])
            .exclude(pk__in=chaine).order_by('pk').first())


def garde_vente_unique(devis, *, user):
    """VNT54 — lève ``VenteActiveExistante`` si le lead porte déjà une vente
    en vigueur hors de la chaîne de ``devis``. Message interne (« Utilisez
    « Prix négocié » ou « Réviser » sur <ref> ») ou neutre pour le client
    (``_acceptation_par_le_client``)."""
    autre = vente_active_hors_chaine(devis)
    if autre is None:
        return
    if _cycle_vie._acceptation_par_le_client(user):
        message = VENTE_ACTIVE_REFUS_CLIENT
    else:
        message = (
            f'Une vente active existe déjà pour ce lead : {autre.reference}. '
            f'Utilisez « Prix négocié » ou « Réviser » sur {autre.reference}.')
    raise VenteActiveExistante(
        message, {'id': autre.pk, 'reference': autre.reference})
