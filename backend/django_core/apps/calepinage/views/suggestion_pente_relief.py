"""ACAL535 — ``POST calepinages/<pk>/suggestions-pente-relief/`` : « Lire la
pente sur un relief de drone ».

L'installateur dépose un GeoTIFF d'altitudes (WGS84, degrés) ; le serveur en
tire une SUGGESTION de pente par pan (``pitchSuggestion`` au statut
``suggeree``, source « relief fourni par l'installateur »), sans la porte du
pays et SANS AUCUN appel à l'altimétrie IGN (``suggerer_pentes(...,
depuis_fichier=True)``). Le fichier n'est pas conservé. La décision
(accepter / refuser) reste celle de ``suggestions-pente/`` (ACAL65) : la
suggestion n'est JAMAIS recopiée dans ``pitchDeg`` (D-ACAL-19).

Corps ``multipart/form-data`` : ``relief`` (le fichier), ``base_empreinte``
(jeton d'écriture), ``zone_id`` (facultatif : un seul pan). Refus 400 nommant
``relief`` (absent, illisible, en mètres, sans pan couvert) ou
``base_empreinte`` ; 409 ``document_modifie`` sur jeton périmé. Société et
droit forcés par ``get_object()`` et ``PeutGererCalepinage``. Rattachée par
``views/rattachements.py``. Contrat : ``calepinage_suggestion_pente.json``.
"""
from __future__ import annotations

import copy

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from core.champs_stricts import ChaineStricte, non_blanc

from ..permissions import PeutGererCalepinage
from ..services.altimetre_fichier import (
    MAX_OCTETS_RELIEF, ReliefIllisible, altimetre_depuis_geotiff)
from ..services.layout import (
    DocumentModifie, LayoutRefuse, _relire_sous_verrou, empreinte_document,
    enregistrer_layout,
)
from ..services.lidar_ign import (
    CLE_SUGGESTION, REFUSEE, SUGGEREE, VALIDEE, suggerer_pentes,
)
from .calepinages import CalepinageViewSet, _reponse_ecriture
from .suggestion_pente import LIBELLE, _zone

__all__ = ['suggestions_pente_relief']

CHAMP_RELIEF = 'relief'
SANS_RELIEF = ("Aucun relief déposé : ajoutez le GeoTIFF d'altitudes de votre "
               "outil de drone (WGS84, degrés).")
SANS_PAN_COUVERT = ("Le relief ne couvre aucun pan de la conception : vérifiez "
                    "qu'il est géoréférencé sur ce site.")


def _refus(champ, message):
    return Response({champ: message}, status=status.HTTP_400_BAD_REQUEST)


def _trace(suggestion):
    """La suggestion du moteur, à la forme du schéma ``suggestionPente``."""
    return {
        'status': SUGGEREE, 'valeurDeg': suggestion.get('pitchDeg'),
        'source': suggestion.get('source'), 'sourceUrl': None,
        'suggestedAt': suggestion.get('suggestedAt'), 'decidedAt': None,
        'libelle': LIBELLE, 'points': suggestion.get('points'),
    }


@extend_schema(
    request=inline_serializer('CalepinageSuggestionReliefCorps', {
        CHAMP_RELIEF: serializers.FileField(),
        'base_empreinte': ChaineStricte(),
        'zone_id': serializers.CharField(required=False)}),
    responses={200: inline_serializer('CalepinageSuggestionRelief', {
        'roof_layout': serializers.DictField(),
        'empreinte_document': serializers.CharField(allow_null=True),
        'layout_hash': serializers.CharField(allow_null=True),
        'inchange': serializers.BooleanField(),
        'version': serializers.IntegerField(allow_null=True)}),
        400: OpenApiResponse(description="Refus nommant « relief » (absent, "
                                         "illisible, en mètres, sans pan couvert) "
                                         "ou « base_empreinte »."),
        409: OpenApiResponse(description="Jeton périmé (document_modifie) ou "
                                         "zone introuvable.")})
@action(detail=True, methods=['post'], url_path='suggestions-pente-relief',
        url_name='suggestions-pente-relief',
        permission_classes=[PeutGererCalepinage],
        parser_classes=[MultiPartParser])
def suggestions_pente_relief(self, request, pk=None):
    """ACAL535 — propose la pente de chaque pan depuis un relief déposé."""
    calepinage = self.get_object()  # L'OBJET D'ABORD (borné société)
    base = request.data.get('base_empreinte')
    base = base.strip() if isinstance(base, str) and non_blanc(base) else ''
    if not base:
        return _refus('base_empreinte',
                      "Jeton manquant : envoyez base_empreinte, l'empreinte "
                      "du document ouvert.")
    # Le JETON avant le fichier : un jeton périmé est refusé à l'écriture
    # (409 ``document_modifie``) quoi que dise le relief — on ne lit donc pas
    # un fichier pour rien. La relecture SOUS VERROU plus bas reste le juge.
    courante = empreinte_document(calepinage.roof_layout)
    if base != courante:
        return Response(DocumentModifie(courante).corps(),
                        status=status.HTTP_409_CONFLICT)
    fichier = request.FILES.get(CHAMP_RELIEF)
    if fichier is not None and fichier.size > MAX_OCTETS_RELIEF:
        return _refus(CHAMP_RELIEF, "Le relief est trop volumineux (maximum "
                      f"{MAX_OCTETS_RELIEF // (1024 * 1024)} Mo).")
    octets = fichier.read() if fichier is not None else b''
    if not octets:
        return _refus(CHAMP_RELIEF, SANS_RELIEF)
    try:
        altimetre = altimetre_depuis_geotiff(octets)
    except ReliefIllisible as refus:
        return _refus(CHAMP_RELIEF, str(refus))

    stocke = calepinage.roof_layout if isinstance(
        calepinage.roof_layout, dict) else {}
    cible = copy.deepcopy(stocke)
    zone_id = request.data.get('zone_id')
    if zone_id not in (None, ''):
        zone = _zone(cible, zone_id)
        if zone is None:
            return Response(
                {'zone_id': f"Zone introuvable dans la conception : {zone_id}."},
                status=status.HTTP_409_CONFLICT)
        cible['zones'] = [zone]
    suggestions = suggerer_pentes(calepinage.company, cible, altimetre=altimetre,
                                  depuis_fichier=True)
    if not suggestions:
        return _refus(CHAMP_RELIEF, SANS_PAN_COUVERT)
    try:
        with transaction.atomic():
            document = copy.deepcopy(_relire_sous_verrou(calepinage, base))
            for suggestion in suggestions:
                pan = _zone(document, suggestion.get('zoneId'))
                existante = pan.get(CLE_SUGGESTION) if pan else None
                if pan is None or (isinstance(existante, dict) and existante.get(
                        'status') in (VALIDEE, REFUSEE)):
                    continue
                pan[CLE_SUGGESTION] = _trace(suggestion)
            resultat = enregistrer_layout(calepinage, document, user=request.user,
                                          base_empreinte=base)
    except DocumentModifie as conflit:
        return Response(conflit.corps(), status=status.HTTP_409_CONFLICT)
    except LayoutRefuse as refus:
        return _refus(refus.champ or 'roof_layout', str(refus))
    return Response(_reponse_ecriture(calepinage, resultat))


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.suggestions_pente_relief = suggestions_pente_relief
