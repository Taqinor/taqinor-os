"""Groupe NTWMS — sélecteurs LECTURE SEULE de la couche entrepôt.

Ré-exporté par ``apps/stock/selectors.py`` (fin de fichier) : les appelants
continuent d'écrire ``from apps.stock.selectors import …``.

FRONTIÈRE INTER-APPS. La hiérarchie de casiers zone/allée/casier existe DÉJÀ
et vit dans ``installations`` (``BinLocation``/``BinAffectation``, FG319 ;
``RegleRangement``/``CategorieStockage``, ZSTK9). Ce module ne la duplique
JAMAIS : il la lit soit par l'accesseur inverse posé sur ``stock.Produit``
(``produit.installations_bin_affectations``), soit via
``apps.installations.selectors`` — jamais en important ses modèles.
"""


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS1 — Localisation d'un produit, CASIER PAR CASIER
# ═══════════════════════════════════════════════════════════════════════════

def localisation_casiers(produit):
    """Localisation casier par casier d'un produit, dans l'ordre de parcours
    physique du magasin.

    Renvoie ``[{bin_id, code, zone, allee, casier, ordre, emplacement_id,
    emplacement_nom, quantite}]`` — liste VIDE tant qu'aucun casier n'est
    affecté (comportement historique préservé). Les casiers archivés sont
    exclus.
    """
    if produit is None:
        return []
    affectations = (produit.installations_bin_affectations
                    .select_related('bin', 'bin__emplacement')
                    .filter(bin__archived=False)
                    .order_by('bin__ordre', 'bin__code'))
    return [{
        'bin_id': aff.bin_id,
        'code': aff.bin.code,
        'zone': aff.bin.zone or '',
        'allee': aff.bin.allee or '',
        'casier': aff.bin.casier or '',
        'ordre': aff.bin.ordre,
        'emplacement_id': aff.bin.emplacement_id,
        'emplacement_nom': (aff.bin.emplacement.nom
                            if aff.bin.emplacement_id else ''),
        'quantite': aff.quantite,
    } for aff in affectations]
