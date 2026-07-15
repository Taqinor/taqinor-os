"""Services du module Achats (``apps.achats``).

ODX20 — ré-export TRANSITOIRE des fonctions de service achats fournisseurs qui
vivent encore physiquement dans ``apps.stock.services`` (elles y étaient
interleavées avec la logique stock). Ce module donne au reste du code (urls,
appelants cross-app) un point d'accès ``apps.achats.services`` stable ; ODX22
re-logera le corps des fonctions ici et retirera ce shim.

FRONTIÈRE STOCK (CLAUDE.md) : les mouvements de stock à la réception/au retour
sont réalisés par ``apps.stock.services`` (``confirm_reception_fournisseur`` /
``apply_retour_fournisseur`` posent les MouvementStock) — ``achats`` ne touche
JAMAIS les modèles stock directement. L'intégration compta (écritures
fournisseurs) continue via ``apps.compta.services``.
"""

from apps.stock.services import (  # noqa: F401
    annuler_reception_confirmee,
    apply_retour_fournisseur,
    cheapest_prix_fournisseur,
    confirm_reception_fournisseur,
    creer_bcf_depuis_lignes,
    dupliquer_bcf,
    facturer_bcf_sur_commande,
    facturer_reception,
    fusionner_bcf,
    generer_bcf_reappro,
    record_purchase_price,
    recompute_facture_fournisseur_statut,
)
