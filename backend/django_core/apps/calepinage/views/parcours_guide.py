"""ACAL392 — ``GET /calepinages/<pk>/parcours/`` : l'état du parcours guidé.

Lecture seule, recalculée à chaque lecture (``services/parcours_guide.py``).
Greffée sur ``CalepinageViewSet`` par affectation d'attribut de classe, comme
les autres actions rattachées (``views/rattachements.py``). La société est
bornée par ``get_object()`` : un calepinage d'une autre société est
INTROUVABLE.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services.parcours_guide import etat_du_parcours
from .calepinages import CalepinageViewSet

__all__ = ['parcours']


@extend_schema(responses={200: inline_serializer('CalepinageParcoursGuide', {
    'etapes': serializers.ListField(child=serializers.DictField()),
    'manque': serializers.ListField(child=serializers.DictField()),
})})
@action(detail=True, methods=['get'], url_path='parcours',
        permission_classes=[PeutVoirCalepinage])
def parcours(self, request, pk=None):
    """L'état des 5 étapes et « ce qui manque » regroupé sans doublon."""
    return Response(etat_du_parcours(self.get_object()))


CalepinageViewSet.parcours = parcours
