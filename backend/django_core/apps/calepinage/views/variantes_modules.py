"""ACAL594 — ``POST calepinages/<pk>/variantes-par-module/``.

Une variante par module coché du stock, sur la même implantation (service
``services/variantes_modules.py``). Greffé au ``CalepinageViewSet`` comme
``views/modules_disponibles.py`` ; la société vient de l'objet résolu, jamais
du corps.
"""
from __future__ import annotations

from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from ..permissions import PeutLireOuEcrireCalepinage
from ..services.variantes import VarianteRefusee
from ..services.variantes_modules import creer_variantes_par_module
from .calepinages import CalepinageViewSet, _statut_refus_variante

__all__ = ['variantes_par_module']


@extend_schema(
    request=drf_serializers.Serializer,
    responses={201: drf_serializers.JSONField()})
@action(detail=True, methods=['post'], url_path='variantes-par-module',
        permission_classes=[PeutLireOuEcrireCalepinage],
        parser_classes=[JSONParser])
def variantes_par_module(self, request, pk=None):
    """ACAL594 — deux modules cochés ⇒ deux variantes nommées par module."""
    from apps.stock.selectors import produits_modules_qs

    calepinage = self.get_object()
    corps = request.data if isinstance(request.data, dict) else {}
    produits = produits_modules_qs(getattr(calepinage, 'company', None))
    try:
        creees = creer_variantes_par_module(
            calepinage, corps.get('modules'), produits, user=request.user)
    except VarianteRefusee as refus:
        return Response({refus.champ or 'modules': str(refus)},
                        status=_statut_refus_variante(refus))
    return Response({
        'calepinage': calepinage.pk,
        'variantes': [
            {'id': c['variante'].pk, 'nom': c['variante'].nom,
             'a_repaver': c['a_repaver']} for c in creees],
    }, status=status.HTTP_201_CREATED)


CalepinageViewSet.variantes_par_module = variantes_par_module
