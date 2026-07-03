"""Récepteurs d'événements métier (M6) — app Contrats.

Abonne ``contrats`` à l'événement ``devis_accepted`` exposé par
``core.events`` pour, à l'acceptation d'un devis DE RENOUVELLEMENT (lié à un
contrat via ``ContratLien`` type ``devis``), marquer le renouvellement proposé
ACCEPTÉ sur le contrat — sans que ``ventes`` importe ``contrats`` (même schéma
que ``apps/crm/receivers.py`` / ``apps/installations/receivers.py``).

Le récepteur est un NO-OP pour tout devis qui n'est PAS un devis de
renouvellement de contrat (aucun ``ContratLien`` correspondant) — la grande
majorité des acceptations de devis (ventes normales) ne déclenchent rien ici.
Ne modifie JAMAIS ``Contrat.statut`` (préservation des statuts — CONTRAT12) ni
n'avance de renouvellement effectif automatique (acte séparé et explicite,
``services.renouveler_contrat`` — CONTRAT23) : seule l'ACCEPTATION est tracée
au chatter (XCTR12).
"""
from django.dispatch import receiver

from core.events import devis_accepted

from .services import marquer_renouvellement_accepte


@receiver(devis_accepted,
          dispatch_uid="contrats_marquer_renouvellement_accepte")
def _marquer_renouvellement_accepte_on_devis_accepted(
        sender, devis, user, ancien_statut, **kwargs):
    """À l'acceptation d'un devis lié à un contrat (ContratLien type devis),
    marque le renouvellement proposé ACCEPTÉ (chatter uniquement — XCTR12).

    Idempotent au sens applicatif : ré-émettre l'événement pour un devis déjà
    accepté ajoute simplement une nouvelle ligne de chatter (jamais une
    exception, jamais de double effet sur le statut du contrat qui n'est de
    toute façon jamais touché ici).
    """
    company = getattr(devis, 'company', None)
    if company is None:
        return

    from .models import ContratLien

    lien = ContratLien.objects.filter(
        company=company, type_cible=ContratLien.TypeCible.DEVIS,
        cible_id=devis.pk,
    ).select_related('contrat').first()
    if lien is None:
        return

    marquer_renouvellement_accepte(lien.contrat, devis, auteur=user)
