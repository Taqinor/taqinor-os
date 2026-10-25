"""ENF18 — ``get_or_create`` d'un ``Produit`` par SKU, point d'entrée cross-app.

Défini ici (``services.py`` est un fichier mur qui ne grossit pas) et ré-exporté par
``apps.stock.services`` : les appelants continuent d'écrire
``from apps.stock.services import get_or_create_produit``.
"""


def get_or_create_produit(company, *, sku, defaults=None):
    """ADEV56 — ``get_or_create`` d'un ``Produit`` de la société sur son ``sku``
    (même contrat que Django : ``(produit, cree)``). Idempotent et course-safe par
    ``unique_together(company, sku)``. Refuse un SKU vide : NULL ≠ NULL en base, un
    produit sans SKU n'est pas dédoublonné et chaque appel en recréerait un."""
    if not sku:
        raise ValueError('Un SKU est requis pour retrouver ou créer un produit.')
    from .models import Produit
    return Produit.objects.get_or_create(
        company=company, sku=sku, defaults=defaults or {})
