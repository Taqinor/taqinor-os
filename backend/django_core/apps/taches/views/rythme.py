"""Rythme, cartes à réponse, préférences dites et en-tête du Copilote (reference/api.md §3.4, §4).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; leur
schéma OpenAPI est celui de leur échantillon de `contract_samples/`.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.taches.views.base import ERREUR_CODE, PERMISSIONS, PasEncore, corps, forme_echantillon, reponses

RYTHME = forme_echantillon('rythme')


class RythmeVue(APIView):
    """GET rythme/ (RYTHME) · POST rythme/ `{"mode","objectif"?,"sens"?}` (seul chemin du mode)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(RYTHME))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=inline_serializer('TachesCorpsRythme', {
        'mode': serializers.CharField(),
        'objectif': serializers.IntegerField(required=False),
        'sens': serializers.CharField(required=False),
    }), responses=reponses(RYTHME, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class RepondrePropositionVue(APIView):
    """POST rythme/propositions/{id}/repondre/ — `{"reponse"}`, toute carte à réponse."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('RepondreProposition', {'reponse': 'oui'}, requis=('reponse',)),
                   responses=reponses(forme_echantillon('proposition_repondue'), erreurs=(400, 404),
                                      conflit=ERREUR_CODE))
    def post(self, request, id):
        raise PasEncore()


class PreferencesVue(APIView):
    """POST preferences/ — poser `{"cle","valeur"}` → RYTHME."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsPreference', {
        'cle': serializers.CharField(),
        'valeur': serializers.JSONField(),
    }), responses=reponses(RYTHME, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class PreferenceVue(APIView):
    """DELETE preferences/{cle}/ — retirer une préférence dite → RYTHME."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(RYTHME, erreurs=(404,)))
    def delete(self, request, cle):
        raise PasEncore()


class CoachEnteteVue(APIView):
    """GET coach/entete/ — deux lignes (≤ 300 caractères) pour le relais du Copilote."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('coach_entete')))
    def get(self, request):
        raise PasEncore()
