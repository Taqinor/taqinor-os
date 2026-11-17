"""L'ERP dans les tâches (reference/api.md §3.1-§3.2, §4 ; conception/spec-6a-erp.md) : « Ailleurs
dans l'ERP », lier et convertir une activité, suggestions.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; leur
schéma OpenAPI est celui de leur échantillon de `contract_samples/`.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.taches.serializers.formes import TacheEcriteSerializer
from apps.taches.views.base import ERREUR_CODE, PERMISSIONS, PasEncore, forme_echantillon, reponses
from core.idempotency import IdempotentCreateMixin


class AilleursVue(APIView):
    """GET aujourdhui/ailleurs/ — compteurs « Ailleurs dans l'ERP » (repli paresseux)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('ailleurs')))
    def get(self, request):
        # TCH56 (lane journee) : le service vit dans services/journee.py ; imports locaux pour ne
        # toucher que ce corps de méthode (le reste du module appartient à la lane erp).
        from rest_framework.response import Response

        from apps.taches.services.journee import ailleurs
        return Response(ailleurs(request.user))


class LierActiviteVue(IdempotentCreateMixin, APIView):
    """POST taches/lier-activite/ — une tâche liée à une activité ERP non close."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsLierActivite', {
        'activite_id': serializers.IntegerField(),
        'titre': serializers.CharField(required=False, max_length=280),
        'jour_prevu': serializers.DateField(required=False, allow_null=True),
    }), responses=reponses(forme_echantillon('lier_activite'), statut=201, erreurs=(400, 404),
                           conflit=ERREUR_CODE))
    def post(self, request):
        raise PasEncore()


class ConvertirActiviteVue(APIView):
    """POST convertir-activite/ — à-faire personnels convertis en tâches (200 partiel)."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsConvertirActivite', {
        'activite_ids': serializers.ListField(required=False, child=serializers.IntegerField()),
        'toutes': serializers.BooleanField(required=False),
    }), responses=reponses(forme_echantillon('convertir_activite'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class SuggestionsVue(APIView):
    """GET suggestions/ — au plus 20 suggestions de l'ERP (moins de 7 jours)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('suggestions')))
    def get(self, request):
        raise PasEncore()


class SuggestionAccepterVue(APIView):
    """POST suggestions/{id}/accepter/ — « Ajouter »."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsSuggestionAccepter', {
        'titre': serializers.CharField(required=False, max_length=280),
        'jour_prevu': serializers.DateField(required=False, allow_null=True),
    }), responses=reponses(TacheEcriteSerializer, statut=201, erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class SuggestionRefuserVue(APIView):
    """POST suggestions/{id}/refuser/ — « Pas utile »."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(forme_echantillon('suggestion_refusee'), erreurs=(404,)))
    def post(self, request, id):
        raise PasEncore()
