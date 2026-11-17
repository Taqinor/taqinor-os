"""Journée, rituels et pastille (reference/api.md §2, §3.1).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction.
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore
from core.idempotency import IdempotentCreateMixin


class AujourdhuiVue(APIView):
    """GET aujourdhui/ — LE contrat de la journée (§2)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class BadgeVue(APIView):
    """GET badge/ — la pastille : ouverts GARDÉS d'Essentiel, Prévu et Ce soir."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class VuVue(APIView):
    """POST vu/ — ouverture du jour ; carte de retour."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class PropositionJourneeVue(APIView):
    """GET journee/proposition/ — la proposition du jour, sans écriture."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class PrioritesVue(APIView):
    """GET journee/priorites/ — « Aide-moi à prioriser »."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class PointVue(APIView):
    """GET journee/point/ — « Où j'en suis ? »."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class PlanifierJourneeVue(IdempotentCreateMixin, APIView):
    """POST journee/planifier/ — « Garder ces N » (mode `express`)."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class EssentielVue(APIView):
    """POST journee/essentiel/ — ★."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class AllegerVue(IdempotentCreateMixin, APIView):
    """POST journee/alleger/ — garder k, le reste aux projets sans report."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class ClotureVue(APIView):
    """GET journee/cloture/ — le contenu du bilan du soir."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class CloturerVue(IdempotentCreateMixin, APIView):
    """POST journee/cloturer/ — clore la journée."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()
