"""CALX359 — la nomenclature de fixation, servie en HTTP.

UNE SEULE FORME D'URL (CAL233) : ``@action`` du viewset pivot, servie sous
``/api/django/calepinage/calepinages/<pk>/bom-fixation/`` — contrat CALX335
(``contract_samples/calepinage_fixation_bom.json``). La réponse est la
sortie de ``services/fixation.py::bom_de_fixation`` MOT POUR MOT :
aucune clé n'est ajoutée ni reformulée ici.

``?systeme=<id>`` désigne le système du catalogue de la société ; à défaut,
l'UNIQUE système actif est appliqué. Un système introuvable, un catalogue
vide ou plusieurs systèmes actifs sans choix sont DITS dans ``refus`` (le
champ ``systeme`` y est nommé), jamais devinés.

Lecture PURE : aucun statut ne bouge, aucun document n'est écrit, aucun
montant n'apparaît (D5). La société vient TOUJOURS du serveur :
``get_object()`` est borné par le queryset du viewset, donc un calepinage
d'une autre société est INTROUVABLE (404), et le système est lu borné à la
société du calepinage.
"""
from __future__ import annotations

from rest_framework import status
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..serializers import corps_obligatoire, forme_du_contrat, forme_reponse
from ..services.fixation import (
    FixationRefusee, appliquer_systeme, bom_de_fixation, resoudre_systeme,
)
from .calepinages import CalepinageViewSet

__all__ = ['bom_fixation', 'fixation']


@extend_schema(
    parameters=[OpenApiParameter(
        'systeme', OpenApiTypes.INT, required=False,
        description='Système de fixation (défaut : celui du calepinage).')],
    responses=forme_du_contrat('CalepinageFixationBom',
                               'calepinage_fixation_bom.json'))
@action(detail=True, methods=['get'], url_path='bom-fixation',
        url_name='bom-fixation', permission_classes=[PeutVoirCalepinage])
def bom_fixation(self, request, pk=None):
    """CALX359 — ``{systeme, lignes, refus, systeme_source}`` (CALX335).

    ACAL81 — sans ``?systeme=``, le système CHOISI sur le calepinage est lu
    avant l'unique système actif.
    """
    calepinage = self.get_object()  # borné société par get_queryset
    demande = request.query_params.get('systeme')
    try:
        if demande is not None:
            # Publié entier : le vide (``?systeme=``) n'en est pas un — il
            # était lu comme « absent » alors que le schéma le déclare faux.
            int(str(demande).strip())
    except ValueError:
        # ERR-ENF11-FUZZ-CALEPINAGE — le paramètre est publié entier : une
        # valeur qui n'en est pas un est refusée, jamais lue comme « absent ».
        return Response(
            {'systeme': "« systeme » attend l'identifiant numérique d'un "
                        f"système de fixation (reçu : « {demande} »)."},
            status=status.HTTP_400_BAD_REQUEST)
    systeme, refus, source = resoudre_systeme(
        calepinage.company, demande,
        calepinage=calepinage, avec_source=True)
    return Response(bom_de_fixation(calepinage, systeme, refus, source))


@extend_schema(
    request=inline_serializer('CalepinageFixationRequete', {
        'systeme_id': drf_serializers.IntegerField(allow_null=True)}),
    responses=forme_reponse('CalepinageFixationChoix', 'systeme',
                            'systeme_source'))
@corps_obligatoire  # corps ABSENT = « Indiquez le système » (400) : le schema l'exige
@action(detail=True, methods=['post'], url_path='fixation',
        url_name='fixation', permission_classes=[PeutGererCalepinage])
def fixation(self, request, pk=None):
    """ACAL81 — ``{systeme_id|null}`` → ``{systeme, systeme_source}``.

    Persiste le système de fixation choisi (``null`` l'efface). Un id absent
    ou d'une autre société : le MÊME 404, champ ``systeme_id`` nommé.
    """
    calepinage = self.get_object()  # borné société par get_queryset
    corps = request.data if isinstance(request.data, dict) else {}
    if 'systeme_id' not in corps:
        return Response(
            {'systeme_id': "Indiquez le système de fixation à appliquer "
                           "(ou null pour retirer le choix)."},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        reponse = appliquer_systeme(calepinage, corps.get('systeme_id'))
    except FixationRefusee as refus:
        return Response({refus.champ: str(refus)},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(reponse)


# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.bom_fixation = bom_fixation
CalepinageViewSet.fixation = fixation  # ACAL81
