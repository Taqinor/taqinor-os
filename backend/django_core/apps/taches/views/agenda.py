"""Agenda (reference/api.md §3.1, §4) : jours (≤ 42), À placer, Mes projets.

Route déclarée : sa vue lève `PasEncore` (501) jusqu'à sa tâche de construction ; son schéma
OpenAPI est celui de l'échantillon `agenda.json`.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore, forme_echantillon, parametre, reponses


class AgendaVue(APIView):
    """GET agenda/ — jours, À placer, Mes projets ; rendez-vous externes du jour."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[
        parametre('du', OpenApiTypes.DATE, 'Premier jour (AAAA-MM-JJ).'),
        parametre('au', OpenApiTypes.DATE, 'Dernier jour ; 42 jours au plus.'),
        parametre('vue', OpenApiTypes.STR, 'jour, semaine, mois ou a-venir.'),
        parametre('projet', OpenApiTypes.INT, "Id d'un de mes projets."),
    ], responses=reponses(forme_echantillon('agenda'), erreurs=(400, 404)))
    def get(self, request):
        raise PasEncore()
