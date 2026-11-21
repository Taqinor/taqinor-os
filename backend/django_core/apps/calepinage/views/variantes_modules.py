"""ACAL594 — ``POST calepinages/<pk>/variantes-par-module/``.

Une variante par module coché du stock, sur la même implantation (service
``services/variantes_modules.py``). Greffé au ``CalepinageViewSet`` comme
``views/modules_disponibles.py`` ; la société vient de l'objet résolu, jamais
du corps.

Le schéma publié et la validation disent la MÊME chose (``RequeteParModule``) :
un tableau de 1 à 3 chaînes ``produit-<entier>``. Une forme fausse ⇒ 400 ; une
forme juste qui désigne un produit inconnu ou une fiche incomplète dépend de
l'état du catalogue ⇒ 409 (ENF11), le champ ``modules`` toujours nommé.
"""
from __future__ import annotations

from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from ..permissions import PeutLireOuEcrireCalepinage
from ..serializers import forme_du_contrat
from ..services.modules_stock import PREFIXE_ID
from ..services.variantes import VarianteRefusee
from ..services.variantes_modules import creer_variantes_par_module
from .calepinages import CalepinageViewSet, _statut_refus_variante

__all__ = ['variantes_par_module', 'RequeteParModule']

#: Au plus trois modules : un comparatif reste lisible (ACAL600).
MODULES_MAX = 3
MOTIF_MODULE = r'^%s[0-9]+$' % PREFIXE_ID
MESSAGE_FORME = (
    f"« modules » est la liste de 1 à {MODULES_MAX} modules à comparer, "
    f"chacun de la forme « {PREFIXE_ID}<numéro> ».")


class RequeteParModule(drf_serializers.Serializer):
    """Le corps : ``{"modules": ["produit-<id>", …]}`` (1 à 3 entrées)."""

    modules = drf_serializers.ListField(
        child=drf_serializers.RegexField(MOTIF_MODULE, max_length=40),
        min_length=1, max_length=MODULES_MAX)


@extend_schema(
    request=RequeteParModule,
    responses={201: forme_du_contrat(
        'CalepinageVariantesParModule',
        'calepinage_variantes_par_module.json')})
@action(detail=True, methods=['post'], url_path='variantes-par-module',
        permission_classes=[PeutLireOuEcrireCalepinage],
        parser_classes=[JSONParser])
def variantes_par_module(self, request, pk=None):
    """ACAL594 — deux modules cochés ⇒ deux variantes nommées par module."""
    from apps.stock.selectors import produits_modules_qs

    calepinage = self.get_object()
    requete = RequeteParModule(
        data=request.data if isinstance(request.data, dict) else {})
    if not requete.is_valid():
        return Response({'modules': MESSAGE_FORME},
                        status=status.HTTP_400_BAD_REQUEST)
    produits = produits_modules_qs(getattr(calepinage, 'company', None))
    try:
        creees = creer_variantes_par_module(
            calepinage, requete.validated_data['modules'], produits,
            user=request.user)
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
