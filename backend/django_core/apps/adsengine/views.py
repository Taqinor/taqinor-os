"""Vues du moteur publicitaire Meta Ads (Groupe ENG).

ENG1 n'expose qu'un endpoint de liveness ``status/`` (``{ok: true}``) — les
ViewSets métier (connexion, garde-fous, actions) atterrissent aux tâches
suivantes de la lane et sont tous basés sur
``core.viewsets.CompanyScopedModelViewSet`` (scoping société garanti).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class StatusView(APIView):
    """ENG1 — Liveness du module publicitaire.

    ``GET /api/django/adsengine/status/`` renvoie ``{"ok": true}`` pour un
    utilisateur authentifié. Ne divulgue aucun secret ni aucune donnée société ;
    sert seulement à confirmer que l'app est installée et routée.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'ok': True})
