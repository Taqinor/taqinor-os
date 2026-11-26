"""D-ACAL-71 (ACAL1318) — « En stock » sur chaque ligne des menus de l'atelier (panneau, onduleur, batterie).

Le stock RÉEL est lu par le sélecteur du stock (``apps.stock.selectors.produits_en_stock``) — jamais ses modèles.
Une ligne porte ``en_stock: True`` quand la société en a (quantité > 0), sinon ``None`` : jamais ``False``, jamais la
quantité, jamais un prix — « non servi » ne s'affiche pas (« rupture » ne se devine pas)."""
from __future__ import annotations


def marquer_en_stock(company, lignes, identifiant):
    """Pose ``en_stock`` (``True`` | ``None``) sur chaque ligne ; ``identifiant(ligne)`` rend l'id produit."""
    lignes = list(lignes or ())
    ids = {identifiant(ligne) for ligne in lignes} - {None}
    servis = set()
    if company is not None and ids:
        from apps.stock.selectors import produits_en_stock

        servis = produits_en_stock(company, ids)
    for ligne in lignes:
        ligne['en_stock'] = True if identifiant(ligne) in servis else None
    return lignes
