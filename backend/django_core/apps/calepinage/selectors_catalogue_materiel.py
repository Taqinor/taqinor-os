"""ACAL960 — le catalogue du matériel de la société, pour choisir les favoris.

Module frère de ``selectors.py`` (qui ne grossit pas) : la Bibliothèque coche
des produits au lieu de taper des identifiants. LECTURE PURE, bornée société,
SANS prix. La notion de « fiche complète » est celle de
``services/electrique.py`` (une seule définition).
"""
from __future__ import annotations

from .selectors import favoris_materiel_de_societe
from .services.electrique import CATEGORIES_CANDIDATS, _champs_manquants

__all__ = ['catalogue_materiel_de_societe']


def catalogue_materiel_de_societe(company):
    """``{modules, onduleurs, optimiseurs}`` : les produits ACTIFS.

    Chaque ligne : ``id``, ``libelle``, ``marque``, ``favori``,
    ``fiche_complete``, ``champs_manquants`` — jamais un prix.
    """
    from apps.stock.selectors import (
        produits_par_type_fiche_qs, specs_for_produit,
    )

    resultat = {cle: [] for cle, _type in CATEGORIES_CANDIDATS}
    if company is None:
        return resultat
    favoris = favoris_materiel_de_societe(company)
    for cle, type_fiche in CATEGORIES_CANDIDATS:
        epingles = {ligne['id'] for ligne in favoris.get(cle, [])}
        for produit in produits_par_type_fiche_qs(company, type_fiche):
            manquants = _champs_manquants(type_fiche,
                                          specs_for_produit(produit))
            resultat[cle].append({
                'id': produit.pk,
                'libelle': (getattr(produit, 'nom', '') or '').strip(),
                'marque': (getattr(produit, 'marque', '') or '').strip(),
                'favori': produit.pk in epingles,
                'fiche_complete': not manquants,
                'champs_manquants': manquants,
            })
    return resultat
