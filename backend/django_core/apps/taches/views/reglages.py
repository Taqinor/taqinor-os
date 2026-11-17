"""Réglages de l'utilisateur et coupe-circuit de la société (reference/api.md §3.4, §4).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction.
`reglages-societe/` est réservé à un administrateur (`IsAdminRole`, A18-M8).
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore
from authentication.permissions import IsAdminRole


class ReglagesVue(APIView):
    """GET reglages/ · PATCH reglages/ (liste blanche)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()

    def patch(self, request):
        raise PasEncore()


class ReglagesSocieteVue(APIView):
    """GET · PATCH reglages-societe/ `{"balayage_actif"}` — administrateur seulement."""

    permission_classes = [*PERMISSIONS, IsAdminRole]

    def get(self, request):
        raise PasEncore()

    def patch(self, request):
        raise PasEncore()
