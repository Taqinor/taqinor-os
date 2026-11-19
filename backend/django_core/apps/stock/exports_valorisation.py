"""STK1 (copilote vague 2, D-ASTK-2 / D-W2-Q6) — export XLSX de la
valorisation du stock selon le droit « voir les prix d'achat ».

``GET stock/produits/valorisation-xlsx/`` est gardée par le seul palier
administrateur : un rôle administrateur dont la case ``prix_achat_voir`` est
décochée recevait le coût moyen et la valeur de chaque ligne. Pour ce compte,
le classeur ne garde que les colonnes de quantité (produit, SKU, emplacement,
quantité) ; un porteur du droit reçoit le classeur complet, inchangé.
"""
from __future__ import annotations

from .permissions import cache_montants_achat

#: Colonnes servies sans le droit : aucune ne porte un coût ni une valeur.
ENTETES_SANS_ACHAT = ('Produit', 'SKU', 'Emplacement', 'Quantité')


def export_valorisation_selon_droit(request):
    """Réponse XLSX de la valorisation de la société de ``request.user`` :
    complète pour un porteur de ``prix_achat_voir``, quantités seules sinon."""
    from apps.records.xlsx import build_xlsx_response

    from .services import export_valorisation_xlsx, stock_valuation_by_location

    company = request.user.company
    if not cache_montants_achat(request):
        return export_valorisation_xlsx(company)
    lignes = stock_valuation_by_location(company)['lignes']
    rows = [[ligne['designation'], ligne['sku'], ligne['emplacement_nom'], ligne['quantite']]
            for ligne in lignes]
    return build_xlsx_response('valorisation.xlsx', list(ENTETES_SANS_ACHAT), rows,
                               sheet_title='Valorisation')
