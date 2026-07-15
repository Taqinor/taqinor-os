"""Vues du module Achats (``apps.achats``).

ODX20 — ré-export TRANSITOIRE des ViewSets achats fournisseurs qui vivent encore
dans ``apps.stock.views`` (adossés à ``TenantMixin`` + ``ModelViewSet`` : scoping
``request.user.company`` + assignation forcée de ``company`` en
``perform_create``). Ce module donne aux nouvelles routes
``/api/django/achats/…`` un point d'entrée ``apps.achats.views`` stable ; les
anciennes routes ``/api/django/stock/…`` continuent de servir les MÊMES classes.
ODX22 re-logera le corps ici.

Les MOUVEMENTS DE STOCK à la réception/au retour passent par
``apps.stock.services`` (confirm_reception_fournisseur / apply_retour_fournisseur)
— jamais par un import direct des modèles stock (frontière services CLAUDE.md).
"""

from apps.stock.views import (  # noqa: F401
    BonCommandeFournisseurViewSet,
    FactureFournisseurViewSet,
    PaiementFournisseurViewSet,
    PrixFournisseurViewSet,
    ReceptionFournisseurViewSet,
    RetourFournisseurViewSet,
)
