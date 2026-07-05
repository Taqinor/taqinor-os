"""Services du module Portail client (``apps.portail``).

ODX12 — ré-export TRANSITOIRE des fonctions de service portail qui vivent encore
physiquement dans ``apps.compta.services`` (elles y étaient interleavées avec la
logique comptable et l'acceptation de devis qui appelle le service ventes
existant). Ce module donne au reste du code (urls, appelants cross-app) un point
d'accès ``apps.portail.services`` stable ; ODX22 re-logera le corps des fonctions
ici et retirera ce shim.

``portail`` ne lit ventes/crm/sav QUE via leurs selectors/services ou par
référence opaque — jamais leurs ``models`` (les fonctions ré-exportées
référencent devis_id/facture_id opaques et passent par le service ventes pour
l'acceptation). ``/proposal`` reste l'unique voie PDF devis (règle #4).
"""

from apps.compta.services import (  # noqa: F401
    initier_paiement_facture,
    rapprocher_paiement_facture,
    signer_acceptation_devis,
)
