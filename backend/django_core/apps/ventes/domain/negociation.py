"""Négociation d'une vente acceptée — Groupe VNT (« Prix négocié », avenant).

Une vente acceptée ne se double pas : un lead porte AU PLUS UNE vente en
vigueur (D-VNT). Un prix renégocié passe par « Prix négocié » (V2 de révision
créée ET acceptée en un geste) ou par « Réviser » — jamais par une seconde
chaîne de devis acceptée à côté de la première (389 acceptée à côté de 388).

Ce module n'écrit AUCUN statut lui-même (règle #4) : il porte les GARDES et
les LECTURES de la négociation ; la bascule reste le seul ``accept_devis``.
Lectures cross-app : aucune (tout est dans ``apps.ventes``). Imports
fonction-locaux : ``cycle_vie`` importe ce module au moment de l'appel.
"""
import logging

logger = logging.getLogger("apps.ventes.services")

#: VNT54 — code machine du 409 (liste FERMÉE ``codes_409`` du contrat
#: ``proposal_accept.json`` ; ``erreurs_409`` de ``devis_prix_negocie.json``).
CODE_VENTE_ACTIVE_EXISTANTE = 'vente_active_existante'

#: VNT54 — message NEUTRE pour le client (lien public, portail) : contrat
#: ``proposal_accept.json`` → ``reponses_409.vente_active_existante``. Aucune
#: référence interne n'est exposée au client.
VENTE_ACTIVE_REFUS_CLIENT = (
    "Cette proposition ne peut pas être signée en l'état : contactez votre "
    'conseiller.')


def vente_active_hors_chaine(devis):
    """VNT54 — la vente en vigueur du lead de ``devis`` qui n'est PAS dans sa
    chaîne de révision (ni ``devis`` lui-même, ni une version qu'il remplace),
    ou ``None``. Un devis sans lead n'a pas de garde (rien à comparer).

    Lecture : ``devis_signes_en_vigueur`` (LA définition de « vente en
    vigueur », VNT22) moins ``devis_predecesseurs_revision_ids`` (une V2 de
    révision remplace sa V1, elle ne la double pas). Une VARIANTE créée depuis
    une vente acceptée n'est pas un prédécesseur : elle est refusée."""
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id or getattr(devis, 'company_id', None) is None:
        return None
    from apps.ventes.selectors import (
        devis_predecesseurs_revision_ids, devis_signes_en_vigueur)
    exclus = set(devis_predecesseurs_revision_ids(devis)) | {devis.pk}
    return (devis_signes_en_vigueur(devis.company, lead_ids=[lead_id])
            .exclude(pk__in=exclus).order_by('pk').first())


def garde_vente_unique(devis, *, user):
    """VNT54 — LA garde « une vente en vigueur par lead » des trois portes
    d'acceptation (vue interne, lien public, portail), posée par
    ``accept_devis`` sous son verrou, AVANT toute écriture.

    Lève ``AcceptError(conflict=True, code='vente_active_existante')`` portant
    ``vente_active = {id, reference}`` ; le message est NEUTRE pour le client
    (``_acceptation_par_le_client``) et dit en interne quel geste utiliser."""
    from apps.ventes.domain.cycle_vie import (
        AcceptError, _acceptation_par_le_client)
    existante = vente_active_hors_chaine(devis)
    if existante is None:
        return
    if _acceptation_par_le_client(user):
        message = VENTE_ACTIVE_REFUS_CLIENT
    else:
        message = (
            f'Ce lead a déjà une vente en vigueur ({existante.reference}). '
            f'Utilisez « Prix négocié » ou « Réviser » sur '
            f'{existante.reference}.')
    exc = AcceptError(message, conflict=True,
                      code=CODE_VENTE_ACTIVE_EXISTANTE)
    exc.vente_active = {'id': existante.pk,
                        'reference': existante.reference}
    logger.info('VNT54: acceptation de %s refusée — vente en vigueur %s '
                'sur le même lead.', getattr(devis, 'reference', '?'),
                existante.reference)
    raise exc
