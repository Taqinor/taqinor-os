"""ACAL403 — ``GET``/``POST``/``DELETE calepinages/profil-depart/``.

Action de LISTE (un réglage société, sans identifiant de calepinage) :
``GET`` rend le profil tel que le fichier le porte (contrat ACAL387) ;
``POST`` remplit les seules clés vides ; ``DELETE`` retire ce que le profil a
posé et qui n'a pas été retouché. Garde PAR MÉTHODE : lire = ``calepinage_voir``,
écrire = ``calepinage_approuver`` (``PERMISSIONS_ECRITURE_PAR_ACTION``).
Société TOUJOURS celle de l'appelant. Code métier : ``services/profil_depart.py``.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuApprouverCalepinage
from ..serializers import forme_du_contrat
from ..services.parametres import ReglageInterdit, ReglageInvalide
from ..services.profil_depart import (
    appliquer_profil, charger_profil, retirer_profil,
)
from .calepinages import CalepinageViewSet

__all__ = ['profil_depart']

_LIGNES = serializers.ListField(child=serializers.DictField())


@extend_schema(methods=['GET'], responses=forme_du_contrat(
    'CalepinageProfilDepart', 'calepinage_profil_depart.json'))
@extend_schema(methods=['POST'], request=None, responses=forme_du_contrat(
    'CalepinageProfilDepartApplication', 'calepinage_profil_depart.json',
    cle='exemple_application'))
@extend_schema(methods=['DELETE'], request=None, responses=inline_serializer(
    'CalepinageProfilDepartRetrait', {'retirees': _LIGNES, 'gardees': _LIGNES}))
@action(detail=False, methods=['get', 'post', 'delete'],
        url_path='profil-depart', url_name='profil-depart',
        permission_classes=[PeutLireOuApprouverCalepinage])
def profil_depart(self, request):
    """ACAL403 — lire, appliquer ou retirer le profil de départ sourcé."""
    methode = request.method.lower()
    if methode == 'get':
        return Response(charger_profil())
    company = getattr(request.user, 'company', None)
    geste = appliquer_profil if methode == 'post' else retirer_profil
    try:
        return Response(geste(company, user=request.user))
    except ReglageInterdit as refus:
        return Response({refus.champ: str(refus)},
                        status=status.HTTP_403_FORBIDDEN)
    except ReglageInvalide as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)


# Le nom d'attribut est EXACTEMENT celui de la fonction (piège CALX7).
CalepinageViewSet.profil_depart = profil_depart
