"""ACAL558 — le catalogue des systèmes de fixation de la société, en HTTP.

Deux ``@action(detail=False)`` du viewset pivot (CAL233 : une seule forme
d'URL), rattachées par ``views/rattachements.py`` — ``urls.py`` n'est pas
touché :

* ``GET``/``POST calepinages/systemes-fixation/`` → ``{systemes}`` / 201
  ``{systeme}`` ;
* ``GET``/``PATCH``/``DELETE calepinages/systemes-fixation/<id>/`` →
  ``{systeme}`` / 204.

Contrat : ``contract_samples/calepinage_systemes_fixation.json`` (ACAL557).
Garde PAR MÉTHODE : lire = ``calepinage_voir``, écrire = ``calepinage_gerer``
(``PeutLireOuEcrireCalepinage``, en cumul avec ``ScopedPermission``). La
société est TOUJOURS celle de l'appelant ; un système d'une autre société est
INTROUVABLE (404), jamais « interdit ». Supprimer un système laisse les
calepinages qui le portaient sans choix (``on_delete=SET_NULL``, ACAL81).
Code métier : ``services/systemes_fixation.py``.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage
from ..serializers import forme_du_contrat, forme_reponse
from ..services.catalogue_fixation import systeme_de_societe
from ..services.systemes_fixation import (
    SystemeRefuse, creer_systeme, liste_des_systemes, modifier_systeme,
    systeme_publie,
)
from .calepinages import CalepinageViewSet

__all__ = ['systemes_fixation', 'systeme_fixation']

_CORPS = inline_serializer('CalepinageSystemeFixationCorps', {
    'code': serializers.CharField(required=False),
    'libelle': serializers.CharField(required=False),
    'fabricant': serializers.CharField(required=False),
    'mode_pose': serializers.CharField(required=False),
    'actif': serializers.BooleanField(required=False),
    'provenance': serializers.CharField(required=False),
    'composants': serializers.ListField(child=serializers.DictField(),
                                        required=False),
})
_UN_SYSTEME = forme_reponse('CalepinageSystemeFixation', 'systeme')


def _company(request):
    return getattr(request.user, 'company', None)


@extend_schema(methods=['GET'], responses=forme_du_contrat(
    'CalepinageSystemesFixation', 'calepinage_systemes_fixation.json'))
@extend_schema(methods=['POST'], request=_CORPS, responses={201: _UN_SYSTEME})
@action(detail=False, methods=['get', 'post'], url_path='systemes-fixation',
        url_name='systemes-fixation',
        permission_classes=[PeutLireOuEcrireCalepinage])
def systemes_fixation(self, request):
    """ACAL558 — lister ou créer un système (composants compris)."""
    company = _company(request)
    if request.method.lower() == 'get':
        return Response(liste_des_systemes(company))
    try:
        systeme = creer_systeme(company, request.data)
    except SystemeRefuse as refus:
        return Response(refus.erreurs, status=status.HTTP_400_BAD_REQUEST)
    return Response({'systeme': systeme}, status=status.HTTP_201_CREATED)


@extend_schema(methods=['GET'], responses=_UN_SYSTEME)
@extend_schema(methods=['PATCH'], request=_CORPS, responses=_UN_SYSTEME)
@extend_schema(methods=['DELETE'], request=None, responses={204: None})
@action(detail=False, methods=['get', 'patch', 'delete'],
        url_path=r'systemes-fixation/(?P<systeme_id>[0-9]+)',
        url_name='systeme-fixation',
        permission_classes=[PeutLireOuEcrireCalepinage])
def systeme_fixation(self, request, systeme_id=None):
    """ACAL558 — lire, modifier (composants remplacés) ou supprimer."""
    systeme = systeme_de_societe(_company(request), systeme_id)
    if systeme is None:
        return Response(
            {'detail': "Système de fixation introuvable dans votre société."},
            status=status.HTTP_404_NOT_FOUND)
    methode = request.method.lower()
    if methode == 'get':
        return Response({'systeme': systeme_publie(systeme)})
    if methode == 'delete':
        systeme.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    try:
        publie = modifier_systeme(systeme, request.data)
    except SystemeRefuse as refus:
        return Response(refus.erreurs, status=status.HTTP_400_BAD_REQUEST)
    return Response({'systeme': publie})


# Le nom d'attribut est EXACTEMENT celui de la fonction (piège CALX7).
CalepinageViewSet.systemes_fixation = systemes_fixation
CalepinageViewSet.systeme_fixation = systeme_fixation
