"""ACAL65 — ``POST /calepinages/<pk>/suggestions-pente/`` : la décision sur une
suggestion de pente IGN, côté serveur (France seule).

Trois opérations, toutes sous le jeton d'écriture ``base_empreinte`` :

* ``proposer`` — ``suggerer_pentes`` sur le document STOCKÉ ; chaque pan qui
  n'a pas déjà une décision reçoit ``pitchSuggestion`` au statut ``suggeree``
  (libellé « pente du terrain »). L'altimètre est appelé HORS verrou ; la
  réécriture relit ensuite le document sous verrou de ligne ;
* ``accepter`` / ``refuser`` — ``lidar_ign.accepter_suggestion`` /
  ``refuser_suggestion`` sur le pan ``zone_id``.

D-ACAL-19 : la suggestion est la pente du TERRAIN. Elle n'écrit JAMAIS
``pitchDeg`` du pan (la production du devis ne dépend jamais d'une donnée IGN)
et ne bloque jamais l'approbation. Base périmée ⇒ 409 ``document_modifie``.
"""
from __future__ import annotations

import copy

from django.db import transaction
from rest_framework import status
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from ..services.layout import (
    DocumentModifie, LayoutRefuse, _relire_sous_verrou, enregistrer_layout,
)
from ..services.lidar_ign import (
    CLE_SUGGESTION, PAYS_COUVERT, REFUSEE, SOURCE, SUGGEREE, URL_SOURCE,
    VALIDEE, ServiceIndisponible, accepter_suggestion, refuser_suggestion,
    suggerer_pentes,
)
from .calepinages import CalepinageViewSet, _reponse_ecriture

__all__ = ['suggestions_pente']

OPERATIONS = ('proposer', 'accepter', 'refuser')
LIBELLE = 'pente du terrain'


def _zone(document, zone_id):
    zones = document.get('zones') if isinstance(document, dict) else None
    return next((z for z in zones or [] if isinstance(z, dict)
                 and str(z.get('id')) == str(zone_id)), None)


def _trace_persistee(suggestion):
    """La suggestion du moteur, mise à la forme du schéma ``suggestionPente``."""
    return {
        'status': SUGGEREE,
        'valeurDeg': suggestion.get('pitchDeg'),
        'source': suggestion.get('source') or SOURCE,
        'sourceUrl': suggestion.get('sourceUrl') or URL_SOURCE,
        'suggestedAt': suggestion.get('suggestedAt'),
        'decidedAt': None,
        'libelle': LIBELLE,
        'points': suggestion.get('points'),
    }


def _proposer(calepinage, base, zone_id, user):
    stocke = calepinage.roof_layout if isinstance(
        calepinage.roof_layout, dict) else {}
    cible = copy.deepcopy(stocke)
    if zone_id not in (None, ''):
        zone = _zone(cible, zone_id)
        if zone is None:
            raise LayoutRefuse(
                f"Zone introuvable dans la conception : {zone_id}.",
                champ='zone_id')
        cible['zones'] = [zone]
    suggestions = suggerer_pentes(calepinage.company, cible)

    with transaction.atomic():
        courant = _relire_sous_verrou(calepinage, base)
        document = copy.deepcopy(courant) if isinstance(courant, dict) else {}
        for suggestion in suggestions:
            pan = _zone(document, suggestion.get('zoneId'))
            if pan is None:
                continue
            existante = pan.get(CLE_SUGGESTION)
            if (isinstance(existante, dict)
                    and existante.get('status') in (VALIDEE, REFUSEE)):
                continue
            pan[CLE_SUGGESTION] = _trace_persistee(suggestion)
        return enregistrer_layout(calepinage, document, user=user,
                                  base_empreinte=base)


def _decider(calepinage, base, zone_id, operation, user):
    if zone_id in (None, ''):
        raise LayoutRefuse("Zone manquante : zone_id est obligatoire.",
                           champ='zone_id')
    with transaction.atomic():
        courant = _relire_sous_verrou(calepinage, base)
        document = copy.deepcopy(courant) if isinstance(courant, dict) else {}
        pan = _zone(document, zone_id)
        if pan is None:
            raise LayoutRefuse(
                f"Zone introuvable dans la conception : {zone_id}.",
                champ='zone_id')
        trace = pan.get(CLE_SUGGESTION)
        if not isinstance(trace, dict):
            raise LayoutRefuse(
                "Aucune suggestion de pente à décider sur ce pan : "
                "proposez-la d'abord.", champ='zone_id')
        if operation == 'accepter':
            accepter_suggestion(pan, trace)
        else:
            refuser_suggestion(pan, trace)
        return enregistrer_layout(calepinage, document, user=user,
                                  base_empreinte=base)


@extend_schema(request=inline_serializer(
    'CalepinageSuggestionsPenteRequete', {
        'operation': drf_serializers.ChoiceField(
            choices=['proposer', 'accepter', 'refuser']),
        'base_empreinte': drf_serializers.CharField(),
        'zone_id': drf_serializers.CharField(required=False),
    }))
@action(detail=True, methods=['post'], url_path='suggestions-pente',
        permission_classes=[PeutGererCalepinage])
def suggestions_pente(self, request, pk=None):
    """ACAL65 — proposer / accepter / refuser une suggestion de pente IGN."""
    calepinage = self.get_object()
    corps = request.data if isinstance(request.data, dict) else {}
    operation = corps.get('operation')
    base = corps.get('base_empreinte')
    if operation not in OPERATIONS:
        return Response(
            {'operation': "Opération inconnue : proposer, accepter ou "
                          "refuser."},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        if not isinstance(base, str) or not base:
            raise LayoutRefuse(
                "Jeton manquant : envoyez base_empreinte, l'empreinte du "
                "document ouvert.", champ='base_empreinte')
        if operation == 'proposer':
            resultat = _proposer(calepinage, base, corps.get('zone_id'),
                                 request.user)
        else:
            resultat = _decider(calepinage, base, corps.get('zone_id'),
                                operation, request.user)
    except ServiceIndisponible as refus:
        return Response(
            {refus.champ or 'detail': str(refus), 'disponible': False,
             'pays_couvert': PAYS_COUVERT, 'source': SOURCE,
             'source_url': URL_SOURCE},
            status=status.HTTP_403_FORBIDDEN)
    except DocumentModifie as conflit:
        return Response(conflit.corps(), status=status.HTTP_409_CONFLICT)
    except LayoutRefuse as refus:
        return Response({refus.champ or 'roof_layout': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(_reponse_ecriture(calepinage, resultat))


CalepinageViewSet.suggestions_pente = suggestions_pente
