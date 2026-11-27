"""ACAL1320 (D-ACAL-73 = corriger_dire, fondateur 26/11/2026) — AVANT « Resynchroniser le devis ».

Ce que la resynchronisation CHANGERA au devis lié, dit avant d'agir : la resynchronisation réelle
jouée puis annulée par ``ventes`` (``apps.ventes.services.apercu_de_resynchronisation``), sur les
MÊMES entrées que ``devis.resynchroniser_devis`` (``_avant_resynchro``, ``_devis_a_resynchroniser``,
``_designations_de`` : feu vert, variante, lecture seule, sélection de surfaces, désignations).
Son refus de statut est le même 409 (``_refus_de_resynchro``) : un devis accepté, refusé ou expiré
se révise, l'aperçu ne l'ouvre pas. Le verdict électrique n'est pas jugé ici : il l'est à la
confirmation, par ``sync-devis``. Contrat : ``contract_samples/calepinage_apercu_resync.json``.
"""
from __future__ import annotations

__all__ = ['apercu_resynchronisation']

#: D-ACAL-106 — les montants d'une ligne retenus pour qui ne lit pas les devis.
CHAMPS_MONTANTS = ('prix_unitaire', 'total_ht', 'prix_unitaire_avant', 'prix_unitaire_apres',
                   'total_ht_avant', 'total_ht_apres')


def _caviarder(reponse):
    """D-ACAL-106 (« aucun devis ni aucun prix ») — mêmes clés ; ni référence, ni montant, ni total.
    La désignation et la quantité restent : elles décrivent la pose. Revue du 26/11 (D-ACAL-165) —
    les avertissements qui portent un montant de vente passent sous leur forme sans montant."""
    from .devis import avertissements_sans_montant  # la porte de ventes (cliquet des imports croisés)

    def _sans_montants(ligne):
        return {cle: (None if cle in CHAMPS_MONTANTS else valeur) for cle, valeur in ligne.items()}

    return dict(reponse, reference=None, totaux=None,
                avertissements=avertissements_sans_montant(reponse.get('avertissements')),
                **{cle: [_sans_montants(li) for li in reponse.get(cle) or ()]
                   for cle in ('ajouts', 'retraits', 'changements')})


def apercu_resynchronisation(calepinage, *, user=None, devis_id=None, surfaces_chiffrees=None,
                             lit_les_devis=True):
    """La forme du contrat ``calepinage_apercu_resync.json`` ; rien n'est écrit.

    Raises:
        DevisRefuse: les mêmes refus que « Resynchroniser le devis » (aucun devis lié, feu vert,
            lecture seule, statut du devis), hors verdict électrique.
    """
    from .devis import (
        _apercu_de_ventes, _avant_resynchro, _designations_de, _devis_a_resynchroniser, _refus_de_resynchro,
    )

    variante, layout = _avant_resynchro(calepinage, devis_id)
    devis, layout = _devis_a_resynchroniser(calepinage, variante, layout, surfaces_chiffrees)
    # Revue du 26/11 — l'aperçu montre ce que la resynchro CONFIRMÉE écrirait (``apercu_confirme``).
    reponse, refus = _apercu_de_ventes(devis, layout, user,
                                       _designations_de(variante or calepinage, apercu_confirme=True))
    if refus is not None:
        raise _refus_de_resynchro(calepinage, devis, refus) from refus
    return reponse if lit_les_devis else _caviarder(reponse)
