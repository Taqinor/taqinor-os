"""ACAL960 — ``GET calepinages/catalogue-materiel/``.

Les produits actifs de la société (modules, onduleurs, optimiseurs), sans prix,
favoris marqués : la Bibliothèque les coche au lieu de saisir des identifiants.
Greffé au ``CalepinageViewSet`` par ``views/rattachements.py`` ; la société
vient de l'utilisateur, jamais de la requête.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..selectors_catalogue_materiel import catalogue_materiel_de_societe
from .calepinages import CalepinageViewSet

__all__ = ['catalogue_materiel']


@extend_schema(responses=drf_serializers.JSONField())
@action(detail=False, methods=['get'], url_path='catalogue-materiel',
        permission_classes=[PeutVoirCalepinage], pagination_class=None)
def catalogue_materiel(self, request):
    """ACAL960 — le catalogue du matériel de la société (lecture pure)."""
    return Response(catalogue_materiel_de_societe(
        getattr(request.user, 'company', None)))


CalepinageViewSet.catalogue_materiel = catalogue_materiel
