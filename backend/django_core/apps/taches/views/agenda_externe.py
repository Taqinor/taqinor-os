"""Agendas externes (reference/api.md §3.4, §4 ; A18-M4) : au plus 3 adresses ICS, lues côté serveur.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction.
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore
from core.idempotency import IdempotentCreateMixin


class AgendasExternesVue(IdempotentCreateMixin, APIView):
    """GET agendas-externes/ (`{"results":[…]}`, ≤ 3) · POST (une adresse ICS, lue aussitôt)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()

    def post(self, request):
        raise PasEncore()


class AgendaExterneVue(APIView):
    """PATCH (libellé, actif, rang) · DELETE agendas-externes/{id}/."""

    permission_classes = PERMISSIONS

    def patch(self, request, id):
        raise PasEncore()

    def delete(self, request, id):
        raise PasEncore()


class AgendaExterneRafraichirVue(APIView):
    """POST agendas-externes/{id}/rafraichir/ — relire maintenant (ignore le cache)."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()
