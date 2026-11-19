"""Copilote vague 2 (STK3) — niveaux de stock COMPACTS lus par l'assistant
(``GET stock/assistant/niveaux/``, action ``stock.produit.niveau``, carte
``niveau_stock``, contrat ``contract_samples/assistant_niveaux.json``).

Des QUANTITÉS seulement, calculées par les mêmes fonctions que la liste
catalogue (``ProduitSerializer``) : réservé aux chantiers, quarantaine qualité,
pipeline des commandes fournisseur ouvertes, seuil effectif (profil saisonnier
actif) et quantité suggérée. ``disponible`` est le chiffre que l'écran Stock
affiche et qu'un commercial peut promettre : stock − réservé − quarantaine.
JAMAIS un prix (vente ou achat) ni une valeur de stock, pour aucun compte.

Portée = celle de la liste produits : société de l'utilisateur, périmètre
d'entités de son rôle, produits archivés exclus. Chaque agrégat est lu UNE
fois (nombre de requêtes fixe, quel que soit le catalogue).
"""
from __future__ import annotations

from django.db.models import Q

LIEN_STOCK = '/stock'
A_FAIRE = ('reapprovisionner', 'rien')


def _produits_visibles(user, q, categorie):
    from core.entite_scoping import scope_entite_queryset

    from .models import Produit

    qs = scope_entite_queryset(
        Produit.objects.filter(company_id=user.company_id, is_archived=False),
        user, 'entite').select_related('categorie')
    for terme in q.split():
        qs = qs.filter(Q(nom__icontains=terme) | Q(marque__icontains=terme)
                       | Q(sku__icontains=terme))
    if categorie:
        qs = qs.filter(categorie_id=categorie)
    return qs.order_by('nom', 'id')


def _agregats(company):
    """Les cartes société lues une seule fois pour toutes les lignes."""
    from .selectors import bcf_sources_en_commande_map
    from .services import (profils_saisonniers_index, quantite_en_quarantaine,
                           reserved_quantities)

    commandes = bcf_sources_en_commande_map(company)
    return {
        'reserve': reserved_quantities(company),
        'quarantaine': quantite_en_quarantaine(company),
        'en_commande': {pid: sum(s['quantite_restante'] for s in sources)
                        for pid, sources in commandes.items()},
        'profils': profils_saisonniers_index(company),
    }


def _ligne(company, produit, agregats):
    from .services import quantite_suggeree_nette, seuil_effectif_produit

    reserve = agregats['reserve'].get(produit.id, 0)
    quarantaine = agregats['quarantaine'].get(produit.id, 0)
    en_commande = agregats['en_commande'].get(produit.id, 0)
    seuil, _cible = seuil_effectif_produit(company, produit, index=agregats['profils'])
    seuil = seuil or 0
    # Seuil d'alerte du catalogue : sur le stock net des réservations
    # (``is_low_stock_disponible``), avec le seuil saisonnier s'il est actif.
    sous_seuil = seuil > 0 and produit.quantite_stock - reserve <= seuil
    suggeree = quantite_suggeree_nette(
        company, produit, disponible=produit.quantite_stock - reserve,
        en_commande=en_commande, index=agregats['profils'])
    return {
        'produit_id': produit.id,
        'nom': produit.nom,
        'marque': produit.marque or '',
        'sku': produit.sku or '',
        'categorie': produit.categorie.nom if produit.categorie_id else '',
        'unite': produit.unite_stock or '',
        'stock': produit.quantite_stock,
        'reserve': reserve,
        'disponible': produit.quantite_stock - reserve - quarantaine,
        'en_commande': en_commande,
        'en_quarantaine': quarantaine,
        'seuil_alerte': seuil,
        'sous_seuil': sous_seuil,
        'quantite_suggeree': suggeree,
        'a_faire': A_FAIRE[0] if sous_seuil and suggeree > 0 else A_FAIRE[1],
        'lien': f'/stock/mouvements?produit={produit.id}',
    }


def niveaux_stock(user, *, q='', categorie=None, sous_seuil=False, limite=10):
    """``(total, lignes)`` — ``total`` compte tous les produits retenus,
    ``lignes`` les ``limite`` premiers par nom. Avec ``sous_seuil`` seuls les
    produits sous leur seuil d'alerte sont retenus."""
    company = user.company
    produits = _produits_visibles(user, q, categorie)
    agregats = _agregats(company)
    if not sous_seuil:
        return produits.count(), [_ligne(company, p, agregats) for p in produits[:limite]]
    lignes = [ligne for ligne in (_ligne(company, p, agregats) for p in produits)
              if ligne['sous_seuil']]
    return len(lignes), lignes[:limite]
