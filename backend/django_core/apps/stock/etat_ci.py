"""État C&I d'un produit — règles partagées par Stock (CCAT1, CCAT2).

Un seul endroit pour « le prix est-il connu ? » : le filtre « C&I à compléter »
(``selectors.etat_ci_produit``) et le catalogue de l'étude
(``selectors.produits_ci``) lisaient deux règles différentes. Lecture seule ;
ne dépend d'aucune autre app (``stock`` n'importe jamais ``ventes``).
"""
from core.product_roles import ROLES_CI_BAREME_COFFRET


def prix_connu_ci(produit, role):
    """Le prix du produit est-il connu pour le moteur C&I ? Prix de vente saisi
    (> 0), OU — pour un coffret tarifé au barème (``ROLES_CI_BAREME_COFFRET``,
    décision fondateur du 26/10/2026) — un prix fixe ou par panneau saisi : le
    moteur le chiffre (``moteur_ci.composition._appliquer_bareme_coffret``).
    Jamais de prix d'achat."""
    if produit.prix_vente and produit.prix_vente > 0:
        return True
    return (role in ROLES_CI_BAREME_COFFRET
            and (produit.prix_fixe_ht is not None
                 or produit.prix_par_panneau_ht is not None))
