"""Mes données (reference/api.md §3.4, §4) : export JSON et « Tout effacer ».

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction.
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore


class MesDonneesVue(APIView):
    """GET mes-donnees/ — export JSON des modèles de l'app."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class ToutEffacerVue(APIView):
    """POST tout-effacer/ — `{"confirmation":"EFFACER"}`, suppression DURE."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()
