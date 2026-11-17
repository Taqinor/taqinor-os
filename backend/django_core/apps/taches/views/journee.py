"""Journée, rituels et pastille (reference/api.md §2, §3.1, §4).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; leur
schéma OpenAPI est celui de leur échantillon de `contract_samples/` (`forme_echantillon`).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.taches.serializers.formes import TacheEcriteSerializer
from apps.taches.views.base import PERMISSIONS, PasEncore, corps, forme_echantillon, parametre, reponses
from core.idempotency import IdempotentCreateMixin

JOUR = parametre('jour', OpenApiTypes.DATE, 'Jour (AAAA-MM-JJ) ; défaut : aujourd\'hui.')
TOUT = parametre('tout', OpenApiTypes.BOOL, '1 : « Voir toutes les tâches de mes projets ».')


class AujourdhuiVue(APIView):
    """GET aujourdhui/ — LE contrat de la journée (§2)."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[JOUR, TOUT], responses=reponses(forme_echantillon('aujourdhui'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()


class BadgeVue(APIView):
    """GET badge/ — la pastille : ouverts GARDÉS d'Essentiel, Prévu et Ce soir."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('badge')))
    def get(self, request):
        raise PasEncore()


class VuVue(APIView):
    """POST vu/ — ouverture du jour ; carte de retour."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('Vu', {'ecran': 'aujourdhui'}),
                   responses=reponses(forme_echantillon('vu'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class PropositionJourneeVue(APIView):
    """GET journee/proposition/ — la proposition du jour, sans écriture."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[
        JOUR, TOUT,
        parametre('exclure', OpenApiTypes.STR, 'Ids de tâches exclues, séparés par des virgules.'),
        parametre('inclure', OpenApiTypes.STR, 'Ids de tâches ajoutées, séparés par des virgules.'),
    ], responses=reponses(forme_echantillon('journee_proposition'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()


class PrioritesVue(APIView):
    """GET journee/priorites/ — « Aide-moi à prioriser »."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[JOUR], responses=reponses(forme_echantillon('priorites'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()


class PointVue(APIView):
    """GET journee/point/ — « Où j'en suis ? »."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('point')))
    def get(self, request):
        raise PasEncore()


class PlanifierJourneeVue(IdempotentCreateMixin, APIView):
    """POST journee/planifier/ — « Garder ces N » (mode `express`)."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('JourneePlanifier', {
        'jour': '2026-11-17', 'mode': 'express', 'lignes': [{'type': 'tache', 'id': 30}],
        'essentielles': [20], 'triage': [],
    }, requis=('jour', 'mode', 'lignes')), responses=reponses(forme_echantillon('journee_ecrite'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class EssentielVue(APIView):
    """POST journee/essentiel/ — ★."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('JourneeEssentiel', {'tache_id': 20, 'essentielle': True},
                                 requis=('tache_id', 'essentielle')),
                   responses=reponses(TacheEcriteSerializer, erreurs=(400, 404)))
    def post(self, request):
        raise PasEncore()


class AllegerVue(IdempotentCreateMixin, APIView):
    """POST journee/alleger/ — garder k, le reste aux projets sans report."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('JourneeAlleger', {'jour': '2026-11-17', 'garder': [20, 42]},
                                 requis=('jour', 'garder')),
                   responses=reponses(forme_echantillon('journee_ecrite'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class ClotureVue(APIView):
    """GET journee/cloture/ — le contenu du bilan du soir."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[JOUR], responses=reponses(forme_echantillon('journee_cloture'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()


class CloturerVue(IdempotentCreateMixin, APIView):
    """POST journee/cloturer/ — clore la journée."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('JourneeCloturer', {
        'jour': '2026-11-17', 'choix': [{'id': 52, 'choix': 'jour', 'jour': '2026-11-23'}],
        'le_reste': True, 'reflexion': '',
    }, requis=('jour',)), responses=reponses(forme_echantillon('journee_cloturee'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()
