"""ACAL485 (D-ACAL-33) — ``GET``/``POST calepinages/<pk>/detection-toit/``.

``GET`` dit si la détection est disponible ; ``POST`` (multipart ``image``,
``emprise``, ``origine``) rend une PROPOSITION de contour et de pans « à
confirmer » — rien n'est écrit, l'image n'est pas stockée. Société forcée par
``self.get_object()`` (``get_queryset`` du viewset pivot : autre société ⇒ 404).
Logique dans ``services/detection_toit.py`` ; contrat ACAL391
``calepinage_detection_toit.json``. Rattachée par ``views/rattachements.py``.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage
from ..services import detection_toit as service
from .calepinages import CalepinageViewSet
from .import_plan import _refus

__all__ = ['detection_toit']

CHAMP_IMAGE = 'image'
REFUS_IMAGE = "Déposez une capture PNG ou JPEG du toit dans le champ « image »."


@extend_schema(methods=['GET'], responses={200: inline_serializer('CalepinageDetectionToitDispo', {
    'disponible': serializers.BooleanField(), 'motif': serializers.CharField(),
    'origines_acceptees': serializers.ListField(child=serializers.CharField())})})
@extend_schema(methods=['POST'], request=inline_serializer('CalepinageDetectionToitCorps', {
    CHAMP_IMAGE: serializers.ImageField(), 'emprise': serializers.CharField(),
    'origine': serializers.ChoiceField(choices=['importee', 'carte'])}),
    responses={200: inline_serializer('CalepinageDetectionToit', {
        'propositions': serializers.DictField(), 'provenance': serializers.CharField(),
        'a_confirmer': serializers.BooleanField()})})
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
    if request.data.get('origine') not in origines:
        return _refus('origine', f"Origine refusée : valeurs acceptées {', '.join(origines)}.")
    emprise = service.lire_emprise(request.data.get('emprise'))
    if emprise is None:
        return _refus('emprise', "Emprise illisible : {ouest, sud, est, nord} en degrés, ouest < est, sud < nord.")
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
