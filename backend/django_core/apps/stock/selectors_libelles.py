"""Copilote vague 2 — libellés des objets Stock (produit, bon de commande
fournisseur, fournisseur) nommés dans l'aperçu d'une proposition de
l'assistant, pour ``GET /api/django/agent/libelles/`` et ``erp.ouvrir``
(résolveur ``libelles_stock`` de la table ``apps/agent/libelles.py``).

Lecture seule, bornée à la SOCIÉTÉ et au droit de LIRE le module Stock (la
garde ``LectureDuModule`` des listes produits, fournisseurs et bons de
commande) ; un produit suit en plus le périmètre d'entités et l'archivage de
sa liste (``ProduitViewSet``). Un objet inconnu, d'une autre société ou hors
portée est ABSENT du résultat, jamais une erreur. Jamais un prix, un stock ni
un montant de commande : un nom, une référence, un statut.
"""


def _joindre(*morceaux):
    return ' — '.join(m for m in ((x or '').strip() for x in morceaux) if m)


def libelles_stock(user, *, produit=None, bcf=None, fournisseur=None):
    """``{'produit': …, 'bcf': …, 'fournisseur': …}`` pour les identifiants
    donnés qui existent dans la société de ``user`` et qu'il a le droit de
    lire (les autres clés manquent)."""
    from authentication.permissions import peut_lire_module
    from core.entite_scoping import scope_entite_queryset

    from .models import BonCommandeFournisseur, Fournisseur, Produit

    societe = getattr(user, 'company_id', None)
    if societe is None or not peut_lire_module(user, 'stock'):
        return {}
    out = {}
    if produit:
        trouve = scope_entite_queryset(
            Produit.objects.filter(company_id=societe, is_archived=False),
            user, 'entite').filter(pk=produit).only('nom', 'sku').first()
        if trouve is not None:
            out['produit'] = _joindre(trouve.nom, trouve.sku)
    if fournisseur:
        trouve = Fournisseur.objects.filter(
            company_id=societe, pk=fournisseur).only('nom').first()
        if trouve is not None and _joindre(trouve.nom):
            out['fournisseur'] = _joindre(trouve.nom)
    if bcf:
        trouve = (BonCommandeFournisseur.objects
                  .filter(company_id=societe, pk=bcf)
                  .select_related('fournisseur').first())
        if trouve is not None:
            nom = trouve.fournisseur.nom if trouve.fournisseur_id else ''
            out['bcf'] = (_joindre(trouve.reference, nom)
                          + f' ({trouve.get_statut_display().lower()})')
    return out
