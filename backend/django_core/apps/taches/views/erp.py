"""L'ERP dans les tâches (reference/api.md §3.1-§3.2, §4 ; conception/spec-6a-erp.md) : « Ailleurs
dans l'ERP », lier et convertir une activité, suggestions.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; leur
schéma OpenAPI est celui de leur échantillon de `contract_samples/`.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.models.rythme import ReglagesRythme
from apps.taches.selectors.base import taches_de
from apps.taches.serializers.formes import TacheEcriteSerializer, charger_taches, contexte, tache_ecrite
from apps.taches.services.erp import PLAFOND_CONVERSION, convertir_activites, lier_activite
from apps.taches.views.base import (
    ERREUR_CODE, PERMISSIONS, PasEncore, est_assistant, forme_echantillon, reponses,
)
from core.idempotency import IdempotentCreateMixin

MESSAGE_REQUIS = 'Requis.'


class _CorpsLier(serializers.Serializer):
    """Corps de `taches/lier-activite/` (api.md §4)."""

    activite_id = serializers.IntegerField(min_value=1)
    titre = serializers.CharField(required=False, allow_blank=True, max_length=280)
    jour_prevu = serializers.DateField(required=False, allow_null=True)


class _CorpsConvertir(serializers.Serializer):
    """Corps de `convertir-activite/` : `{"activite_ids":[…]}` ou `{"toutes":true}` (api.md §4)."""

    activite_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=False,
        max_length=PLAFOND_CONVERSION)
    toutes = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get('toutes') and not attrs.get('activite_ids'):
            raise serializers.ValidationError({'activite_ids': [MESSAGE_REQUIS]})
        return attrs


def _tache_ecrite(request, tache_id, geste):
    """TACHE_ECRITE de la tâche `tache_id` de l'utilisateur, relue avec tout ce qu'elle sert."""
    user = request.user
    tache = charger_taches(taches_de(user).filter(pk=tache_id)).get()
    reglages = ReglagesRythme.objects.filter(company_id=user.company_id, proprietaire=user).first()
    instance = tache_ecrite(tache, geste_id=geste.pk if geste is not None else None)
    return TacheEcriteSerializer(
        instance, context=contexte(assistant=est_assistant(request), reglages=reglages)).data


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
        return self._avec_idempotence(request, lambda: self._lier(request))

    def _lier(self, request):
        corps = _CorpsLier(data=request.data)
        corps.is_valid(raise_exception=True)
        donnees = corps.validated_data
        resultat = lier_activite(request.user, activite_id=donnees['activite_id'],
                                 titre=donnees.get('titre', ''), jour_prevu=donnees.get('jour_prevu'))
        return Response(_tache_ecrite(request, resultat.creees[0].pk, resultat.geste),
                        status=status.HTTP_201_CREATED)


class ConvertirActiviteVue(APIView):
    """POST convertir-activite/ — à-faire personnels convertis en tâches (200 partiel)."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsConvertirActivite', {
        'activite_ids': serializers.ListField(required=False, child=serializers.IntegerField()),
        'toutes': serializers.BooleanField(required=False),
    }), responses=reponses(forme_echantillon('convertir_activite'), erreurs=(400,)))
    def post(self, request):
        corps = _CorpsConvertir(data=request.data)
        corps.is_valid(raise_exception=True)
        donnees = corps.validated_data
        return Response(convertir_activites(request.user, ids=donnees.get('activite_ids') or (),
                                            toutes=donnees['toutes']))


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
