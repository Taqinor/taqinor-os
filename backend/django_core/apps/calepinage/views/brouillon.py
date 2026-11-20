"""ACAL400 — ``GET``/``PUT``/``DELETE calepinages/<pk>/brouillon/``.

Le brouillon d'atelier de l'APPELANT (jamais celui d'un autre), rangé côté
serveur pour être repris depuis un autre poste (contrat
``contract_samples/calepinage_brouillon.json``). ``GET`` rend le brouillon à
jour ou ``null`` (absent ou périmé) ; ``PUT`` le range et le rend ; ``DELETE``
l'efface et rend ``null``. Garde PAR MÉTHODE (``PeutLireOuEcrireCalepinage``) ;
un calepinage d'une autre société est introuvable (404, ``get_object``). Le
code métier vit dans ``services/brouillon.py``.

Greffe par AFFECTATION d'attribut (nom == ``fonction.__name__``) ; l'import
qui exécute ce module est en FIN de ``views/rattachements.py``.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage
from ..serializers import corps_obligatoire
from .calepinages import CalepinageViewSet
from .meteo_fichier import _RenduJsonNull

__all__ = ['brouillon']

#: Le brouillon, ou ``null`` (``allow_null`` d'un ``inline_serializer`` n'est
#: pas publié par drf-spectacular : schéma brut, comme ``meteo-fichier``).
_BROUILLON_OU_NULL = {
    'type': 'object', 'nullable': True,
    'properties': {'layout': {'type': 'object'},
                   'horodatage': {'type': 'string'},
                   'base_empreinte': {'type': 'string'}},
    'required': ['layout', 'horodatage', 'base_empreinte'],
}


@extend_schema(methods=['GET'], responses={200: _BROUILLON_OU_NULL})
@extend_schema(
    methods=['PUT'],
    request=inline_serializer('CalepinageBrouillonCorps', {
        'layout': serializers.JSONField(),
        'horodatage': serializers.CharField(max_length=40),
        'base_empreinte': serializers.CharField(max_length=64,
                                                allow_blank=True)}),
    responses={200: _BROUILLON_OU_NULL})
@extend_schema(methods=['DELETE'], responses={200: _BROUILLON_OU_NULL})
@corps_obligatoire
@action(detail=True, methods=['get', 'put', 'delete'],
        url_path='brouillon', url_name='brouillon',
        permission_classes=[PeutLireOuEcrireCalepinage],
        parser_classes=[JSONParser], renderer_classes=[_RenduJsonNull])
def brouillon(self, request, pk=None):
    """ACAL400 — lire, ranger ou effacer MON brouillon d'atelier."""
    from ..services.brouillon import (
        BrouillonRefuse, effacer_brouillon, enregistrer_brouillon,
        lire_brouillon,
    )

    calepinage = self.get_object()  # borné société par get_queryset
    if request.method == 'GET':
        return Response(lire_brouillon(calepinage, request.user))
    if request.method == 'DELETE':
        effacer_brouillon(calepinage, request.user)
        return Response(None)
    try:
        return Response(enregistrer_brouillon(calepinage, request.user,
                                              request.data))
    except BrouillonRefuse as refus:
        return Response({refus.champ: str(refus)},
                        status=(status.HTTP_409_CONFLICT if refus.conflit
                                else status.HTTP_400_BAD_REQUEST))


# Rattachement au viewset PIVOT (patron CALX2, ``views/rattachements.py``).
CalepinageViewSet.brouillon = brouillon
