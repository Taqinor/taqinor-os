"""ASTK257 (C-ASTK-VER4-040) — LA lecture « déjà sorti » d'une vente, lue
par chantiers et stock par la FAÇADE ``apps.ventes.selectors`` (ré-export en
fin de fichier) sans importer ``ventes.domain``. Module PLAT : aucun import
de ``.selectors`` en tête (cycle)."""


def sorties_de_la_vente(devis_id, company):
    """``{produit_id: Decimal}`` — Σ des SORTIES sous la référence du devis,
    de ses BC et de son chantier, chaque mouvement compté une fois, NETTES
    des ENTRÉES sous ces références (ASTK262 : stock rendu par l'annulation
    d'une facture), bornées à 0. Devis inconnu ou d'une autre société :
    ``{}``. Ne lit jamais ``quantite_deja_sortie_chantier`` (pas de boucle
    avec le chantier)."""
    from decimal import Decimal
    from apps.installations.selectors import installation_for_devis
    from apps.stock.selectors import mouvements_par_reference
    from apps.stock.services import (
        mouvement_type_entree, mouvement_type_sortie,
    )
    from .models import BonCommande, Devis
    from .selectors import devis_de_la_societe, devis_predecesseurs_revision_ids
    try:
        devis = devis_de_la_societe(devis_id, company)
    except Devis.DoesNotExist:
        return {}
    inst = installation_for_devis(devis, company=company)
    # ASTK264 — + les versions que la vente REMPLACE par révision (et leurs BC) :
    # la SORTIE d'une facture de V1 reste posée sous ``V1.reference``.
    ventes = [devis.pk, *devis_predecesseurs_revision_ids(devis)]
    refs = {devis.reference, getattr(inst, 'reference', None), *(
        Devis.objects.filter(pk__in=ventes[1:], company=company)
        .values_list('reference', flat=True)), *(
        BonCommande.objects.filter(devis_id__in=ventes, company=company)
        .values_list('reference', flat=True))} - {None, ''}
    signe = {mouvement_type_sortie(): 1, mouvement_type_entree(): -1}
    vus, sorti = set(), {}
    for ref in refs:
        for mid, pid, typ, qte in (
                mouvements_par_reference(company, ref)
                .filter(type_mouvement__in=list(signe))
                .values_list('id', 'produit_id', 'type_mouvement',
                             'quantite')):
            if mid not in vus:
                vus.add(mid)
                sorti[pid] = (sorti.get(pid, Decimal('0'))
                              + signe[typ] * Decimal(qte))
    return {pid: q for pid, q in sorti.items() if q > 0}
