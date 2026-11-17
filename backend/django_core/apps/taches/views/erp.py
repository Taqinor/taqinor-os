"""L'ERP dans les tâches (reference/api.md §3.1-§3.2 ; conception/spec-6a-erp.md) : « Ailleurs dans
l'ERP », lier et convertir une activité, suggestions.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction.
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore
from core.idempotency import IdempotentCreateMixin


class AilleursVue(APIView):
    """GET aujourdhui/ailleurs/ — compteurs « Ailleurs dans l'ERP » (repli paresseux)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class LierActiviteVue(IdempotentCreateMixin, APIView):
    """POST taches/lier-activite/ — une tâche liée à une activité ERP non close."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class ConvertirActiviteVue(APIView):
    """POST convertir-activite/ — à-faire personnels convertis en tâches (200 partiel)."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class SuggestionsVue(APIView):
    """GET suggestions/ — au plus 20 suggestions de l'ERP (moins de 7 jours)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class SuggestionAccepterVue(APIView):
    """POST suggestions/{id}/accepter/ — « Ajouter »."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class SuggestionRefuserVue(APIView):
    """POST suggestions/{id}/refuser/ — « Pas utile »."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()
