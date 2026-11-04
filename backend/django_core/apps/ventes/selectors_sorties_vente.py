"""ASTK257 (C-ASTK-VER4-040) — LA lecture « déjà sorti » d'une vente, lue
par chantiers et stock par la FAÇADE ``apps.ventes.selectors`` (ré-export en
fin de fichier) sans importer ``ventes.domain``. Module PLAT : aucun import
de ``.selectors`` en tête (cycle)."""


def sorties_de_la_vente(devis_id, company):
    """``{produit_id: Decimal}`` — Σ des SORTIES sous la référence du devis,
    de ses BC et de son chantier, chaque mouvement compté une fois. Devis
    inconnu ou d'une autre société : ``{}``. Ne lit jamais
    ``quantite_deja_sortie_chantier`` (pas de boucle avec le chantier)."""
    from decimal import Decimal
    from apps.installations.selectors import installation_for_devis
    from apps.stock.selectors import mouvements_par_reference
    from apps.stock.services import mouvement_type_sortie
    from .models import BonCommande, Devis
    from .selectors import devis_de_la_societe
    try:
        devis = devis_de_la_societe(devis_id, company)
    except Devis.DoesNotExist:
        return {}
    inst = installation_for_devis(devis, company=company)
    refs = {devis.reference, getattr(inst, 'reference', None), *(
        BonCommande.objects.filter(devis=devis, company=company)
        .values_list('reference', flat=True))} - {None, ''}
    vus, sorti = set(), {}
    for ref in refs:
        for mid, pid, qte in (mouvements_par_reference(company, ref)
                              .filter(type_mouvement=mouvement_type_sortie())
                              .values_list('id', 'produit_id', 'quantite')):
            if mid not in vus:
                vus.add(mid)
                sorti[pid] = sorti.get(pid, Decimal('0')) + Decimal(qte)
    return sorti
