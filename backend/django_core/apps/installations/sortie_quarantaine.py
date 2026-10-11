"""ASTK249 — sortie de stock d'un chantier hors quarantaine.

Module séparé : `services.py` est un fichier-mur.
"""


def sortie_hors_quarantaine(company, produit, qte_avant, demandee):
    """`(qte_sortie, en_quarantaine)` : la part en quarantaine (rappel,
    réception non conforme) ne sort jamais au nom du chantier ; la sortie est
    bornée au stock disponible (jamais négatif — ERR80)."""
    from apps.stock.services import quantite_disponible_hors_quarantaine

    dispo = min(qte_avant, quantite_disponible_hors_quarantaine(
        company, produit))
    sortie = min(demandee, dispo) if dispo > 0 else 0
    manquant = demandee - sortie
    return sortie, (min(manquant, max(qte_avant - dispo, 0))
                    if manquant > 0 else 0)


def detail_manques(manques):
    """Libellé des manques `(réf, manquant, en quarantaine)`."""
    return ', '.join(
        f'{ref} (manque {manquant}'
        + (f', dont {en_q} en quarantaine)' if en_q else ')')
        for ref, manquant, en_q in manques)
