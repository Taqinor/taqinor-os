"""ACAL485 (D-ACAL-33) — ``GET``/``POST calepinages/<pk>/detection-toit/``.

``GET`` dit si la détection est disponible ; ``POST`` (multipart ``image``,
``emprise``, ``origine``) rend une PROPOSITION de contour et de pans « à
confirmer » — rien n'est écrit, l'image n'est pas stockée. Société forcée par
``self.get_object()`` (``get_queryset`` du viewset pivot : autre société ⇒ 404).
Logique dans ``services/detection_toit.py`` ; contrat ACAL391
``calepinage_detection_toit.json``. Rattachée par ``views/rattachements.py``.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE

from ..permissions import PeutLireOuEcrireCalepinage
from ..services import detection_toit as service
from .calepinages import CalepinageViewSet
from .import_plan import _refus

__all__ = ['detection_toit']

CHAMP_IMAGE = 'image'
REFUS_IMAGE = "Déposez une capture PNG ou JPEG du toit dans le champ « image »."

#: La FORME exacte de l'emprise (un objet JSON, chaque coin dans ses bornes),
#: publiée en ``x-corps-resserre`` sans changer de composant : ce qui la viole
#: est un 400 ; ouest >= est ou sud >= nord (contrainte croisée, indicible au
#: schéma) est un 409 — api-fuzz #1512 : une requête conforme n'est jamais 400.
_EMPRISE_RESSERREE = {EXTENSION_CORPS_RESSERRE: {'properties': {'emprise': {
    'type': 'object', 'required': list(service.BORNES_COINS),
    'properties': {coin: {'type': 'number', 'minimum': bas, 'maximum': haut}
                   for coin, (bas, haut) in service.BORNES_COINS.items()}}}}}


@extend_schema(methods=['GET'], responses={200: inline_serializer('CalepinageDetectionToitDispo', {
    'disponible': serializers.BooleanField(), 'motif': serializers.CharField(),
    'origines_acceptees': serializers.ListField(child=serializers.CharField())})})
@extend_schema(methods=['POST'], extensions=_EMPRISE_RESSERREE,
               request=inline_serializer('CalepinageDetectionToitCorps', {
                   CHAMP_IMAGE: serializers.ImageField(),
                   'emprise': serializers.DictField(child=serializers.FloatField()),
                   'origine': serializers.ChoiceField(choices=list(service.ORIGINES))}),
               responses={200: inline_serializer('CalepinageDetectionToit', {
                   'propositions': serializers.DictField(), 'provenance': serializers.CharField(),
                   'a_confirmer': serializers.BooleanField()}),
                   503: OpenApiResponse(description=service.DETAIL_INDISPONIBLE)})
@action(detail=True, methods=['get', 'post'], url_path='detection-toit', url_name='detection-toit',
        permission_classes=[PeutLireOuEcrireCalepinage], parser_classes=[MultiPartParser])
def detection_toit(self, request, pk=None):
    """ACAL485 — disponibilité (GET) ou proposition IA à confirmer (POST)."""
    from apps.ventes import services as ventes_services

    from ..services.photos import MAX_OCTETS

    calepinage = self.get_object()  # L'OBJET D'ABORD (borné société)
    if request.method == 'GET':
        return Response(service.disponibilite(calepinage.company_id))
    origines = service.origines_acceptees()
    origine = request.data.get('origine')
    if origine not in service.ORIGINES:
        return _refus('origine', f"Origine refusée : valeurs acceptées {', '.join(origines)}.")
    if origine not in origines:  # connue mais fermée par le réglage : 409
        return Response({'origine': f"Origine « {origine} » non ouverte sur ce serveur : "
                                    f"valeurs acceptées {', '.join(origines)}."},
                        status=status.HTTP_409_CONFLICT)
    brut = request.data.get('emprise')
    if service.coins_emprise(brut) is None:
        return _refus('emprise', "Emprise illisible : {ouest, sud, est, nord} en degrés "
                                 "(longitudes -180 à 180, latitudes -90 à 90).")
    emprise = service.lire_emprise(brut)
    if emprise is None:
        return Response({'emprise': "Emprise incohérente : ouest < est et sud < nord attendus."},
                        status=status.HTTP_409_CONFLICT)
    fichier = request.FILES.get(CHAMP_IMAGE)
    donnees = fichier.read() if fichier is not None else b''
    if len(donnees) > MAX_OCTETS:
        return _refus(CHAMP_IMAGE, f"Image trop volumineuse : {MAX_OCTETS // (1024 * 1024)} Mo au maximum.")
    _extension, mime = ventes_services.type_image_toiture(donnees)
    if mime not in ('image/png', 'image/jpeg'):
        return _refus(CHAMP_IMAGE, REFUS_IMAGE)
    try:
        propositions = service.detecter(calepinage.company_id, donnees, mime, emprise)
    except service.DetectionIndisponible:
        return Response({'detail': service.DETAIL_INDISPONIBLE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'propositions': propositions, 'provenance': 'ia', 'a_confirmer': True})


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.detection_toit = detection_toit
