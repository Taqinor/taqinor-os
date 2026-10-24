"""Aides de ``services.py`` (fichier-mur) sorties ici — lecture bornée."""


def produit_scope_ou_none(company, produit_id):
    """Produit de la société désigné par ``produit_id``, ou ``None`` (absent,
    illisible ou d'une autre société)."""
    from apps.stock.selectors import get_produit_scoped

    if not produit_id:
        return None
    try:
        return get_produit_scoped(company, produit_id)
    except (TypeError, ValueError):
        return None
