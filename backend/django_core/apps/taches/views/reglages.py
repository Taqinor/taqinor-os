"""Réglages de l'utilisateur et coupe-circuit de la société (reference/api.md §3.4, §4).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; leur
schéma OpenAPI est celui de leur échantillon de `contract_samples/`. `reglages-societe/` est
réservé à un administrateur (`IsAdminRole`, A18-M8).
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore, corps, forme_echantillon, reponses
from authentication.permissions import IsAdminRole

REGLAGES = forme_echantillon('reglages')
REGLAGES_SOCIETE = forme_echantillon('reglages_societe')


class ReglagesVue(APIView):
    """GET reglages/ · PATCH reglages/ (liste blanche)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(REGLAGES))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=inline_serializer('TachesCorpsReglages', {
        'titres_notifications': serializers.BooleanField(required=False),
        'titres_calendrier': serializers.BooleanField(required=False),
        'titres_tuile': serializers.BooleanField(required=False),
        'messages_sans_delai': serializers.BooleanField(required=False),
        'rappel_avant_bloc_min': serializers.IntegerField(required=False, allow_null=True),
        'projet_arret_jours': serializers.IntegerField(required=False),
        'familles_suggestions': serializers.ListField(required=False, child=serializers.CharField()),
        'suggestions_societe': serializers.BooleanField(required=False),
        'erp_dans_journee': serializers.BooleanField(required=False),
        'comprendre_mon_rythme': serializers.BooleanField(required=False),
        'pauses_sollicitations': serializers.ListField(required=False, child=serializers.DictField()),
    }), responses=reponses(REGLAGES, erreurs=(400,)))
    def patch(self, request):
        raise PasEncore()


class ReglagesSocieteVue(APIView):
    """GET · PATCH reglages-societe/ `{"balayage_actif"}` — administrateur seulement."""

    permission_classes = [*PERMISSIONS, IsAdminRole]

    @extend_schema(responses=reponses(REGLAGES_SOCIETE))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=corps('ReglagesSociete', {'balayage_actif': False}, requis=('balayage_actif',)),
                   responses=reponses(REGLAGES_SOCIETE, erreurs=(400,)))
    def patch(self, request):
        raise PasEncore()
