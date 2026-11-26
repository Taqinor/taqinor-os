"""D-ACAL-71 (ACAL1318) — « En stock » d'un produit, lu par les autres apps (frontière d'application : selectors)."""
from __future__ import annotations


def produits_en_stock(company, ids):
    """L'ensemble des ids (parmi ``ids``) dont le stock RÉEL de la société est > 0.

    CHOIX : « en stock » = ``quantite_stock > 0``, la même définition que la composition des devis
    (``ventes/domain/catalogue.py::_batterie_en_stock``), c'est-à-dire PHYSIQUEMENT présent — pas le « disponible »
    de l'écran de stock (moins réservations et quarantaine).

    Lecture seule, une requête, bornée à ``company`` ; ni prix ni quantité n'en sortent : un produit à 0 n'entre pas
    dans l'ensemble (l'appelant n'affiche alors RIEN pour lui)."""
    from .models import Produit

    return set(Produit.objects.filter(company=company, pk__in=list(ids), quantite_stock__gt=0)
               .values_list('pk', flat=True))
