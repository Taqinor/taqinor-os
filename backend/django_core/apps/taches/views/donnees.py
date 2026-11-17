"""Mes données (reference/api.md §3.4, §4) : export JSON et « Tout effacer ».

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; leur
schéma OpenAPI est celui de leur échantillon de `contract_samples/`.
"""
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore, corps, forme_echantillon, reponses


class MesDonneesVue(APIView):
    """GET mes-donnees/ — export JSON des modèles de l'app."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('mes_donnees')))
    def get(self, request):
        raise PasEncore()


class ToutEffacerVue(APIView):
    """POST tout-effacer/ — `{"confirmation":"EFFACER"}`, suppression DURE."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('ToutEffacer', {'confirmation': 'EFFACER'}, requis=('confirmation',)),
                   responses=reponses(forme_echantillon('tout_effacer'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()
