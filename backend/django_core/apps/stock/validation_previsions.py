"""Date de rupture et point de commande d'un produit (extrait de ``services.py``, C20)."""
from core.stock_reorder import predict_reorder


def rupture_prevue(produit, today, conso_jour):
    """``{'date_rupture', 'point_commande'}`` du produit.

    ENF11 nocturne - stock enorme / conso minuscule : la date de rupture
    depasse l'an 9999 (OverflowError -> 500). Pas de rupture previsible : date
    nulle, point de commande = stock de securite.
    """
    try:
        reorder = predict_reorder(
            current_stock=produit.quantite_stock, today=today,
            avg_daily_consumption=conso_jour,
            safety_stock=produit.seuil_alerte or 0)
        return {'date_rupture': reorder.rupture_date,
                'point_commande': reorder.reorder_point}
    except OverflowError:
        return {'date_rupture': None,
                'point_commande': float(produit.seuil_alerte or 0)}
