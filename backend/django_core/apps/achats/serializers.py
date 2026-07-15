"""Serializers du module Achats (``apps.achats``).

ODX20 — ré-export TRANSITOIRE des serializers achats fournisseurs qui vivent
encore dans ``apps.stock.serializers`` (interleavés avec les serializers stock).
Ce module expose ``apps.achats.serializers`` pour les ViewSets achats et les
nouvelles routes ``/api/django/achats/…`` ; ODX22 re-logera leur corps ici. Les
routes historiques ``/api/django/stock/…`` continuent d'utiliser les MÊMES
classes.
"""

from apps.stock.serializers import (  # noqa: F401
    BonCommandeFournisseurSerializer,
    FactureFournisseurSerializer,
    LigneBonCommandeFournisseurSerializer,
    LigneFactureFournisseurSerializer,
    LigneReceptionFournisseurSerializer,
    LigneRetourFournisseurSerializer,
    PaiementFournisseurSerializer,
    PrixFournisseurSerializer,
    ReceptionFournisseurSerializer,
    RetourFournisseurSerializer,
)
