"""Agenda (reference/api.md §3.1) : jours (≤ 42), À placer, Mes projets.

Route déclarée : sa vue lève `PasEncore` (501) jusqu'à sa tâche de construction.
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore


class AgendaVue(APIView):
    """GET agenda/ — jours, À placer, Mes projets ; rendez-vous externes du jour."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()
