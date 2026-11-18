"""Mes données (reference/api.md §3.4, §4) : export JSON et « Tout effacer ».

Le compte et la société sont ceux de la requête, jamais lus du corps ; « Tout effacer » n'a pas de
geste (api.md §4 « Sans `geste_id` »).
"""
from collections.abc import Mapping

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.services.donnees import exporter, tout_effacer
from apps.taches.views.base import PERMISSIONS, corps, forme_echantillon, reponses
from apps.taches.views.presence import HorsAssistant

CONFIRMATION = 'EFFACER'
MESSAGE_CONFIRMATION = 'Tape EFFACER pour confirmer.'


class ExportHorsAssistant(HorsAssistant):
    """403 sous l'en-tête assistant (api.md §0) : l'export porte tout, le contenu confidentiel compris."""

    message = "L'assistant ne lit pas l'export de tes données."


class MesDonneesVue(APIView):
    """GET mes-donnees/ — export JSON des modèles de l'app ; jamais servi au relais de l'assistant."""

    permission_classes = [*PERMISSIONS, ExportHorsAssistant]

    @extend_schema(responses=reponses(forme_echantillon('mes_donnees')))
    def get(self, request):
        reponse = Response(exporter(request.user))
        reponse['Cache-Control'] = 'no-store'
        return reponse


class ToutEffacerVue(APIView):
    """POST tout-effacer/ — `{"confirmation":"EFFACER"}`, suppression DURE."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('ToutEffacer', {'confirmation': 'EFFACER'}, requis=('confirmation',)),
                   responses=reponses(forme_echantillon('tout_effacer'), erreurs=(400,)))
    def post(self, request):
        donnees = request.data if isinstance(request.data, Mapping) else {}
        if str(donnees.get('confirmation') or '').strip() != CONFIRMATION:
            raise serializers.ValidationError({'confirmation': [MESSAGE_CONFIRMATION]})
        return Response(tout_effacer(request.user))
