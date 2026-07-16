"""Vues du moteur publicitaire Meta Ads (Groupe ENG).

ENG1 n'expose qu'un endpoint de liveness ``status/`` (``{ok: true}``) — les
ViewSets métier (connexion, garde-fous, actions) atterrissent aux tâches
suivantes de la lane et sont tous basés sur
``core.viewsets.CompanyScopedModelViewSet`` (scoping société garanti).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.viewsets import CompanyScopedModelViewSet

from .models import MetaConnection
from .serializers import MetaConnectionSerializer


class StatusView(APIView):
    """ENG1 — Liveness du module publicitaire.

    ``GET /api/django/adsengine/status/`` renvoie ``{"ok": true}`` pour un
    utilisateur authentifié. Ne divulgue aucun secret ni aucune donnée société ;
    sert seulement à confirmer que l'app est installée et routée.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'ok': True})


class AdsengineViewSet(CompanyScopedModelViewSet):
    """Base des ViewSets du moteur publicitaire.

    Hérite de ``CompanyScopedModelViewSet`` (scoping ``request.user.company`` +
    forçage société côté serveur garantis, SCA4). Gate lecture/écriture par les
    permissions fines ``adsengine_view`` / ``adsengine_manage`` (lues par
    ``ScopedPermission`` selon la méthode HTTP). L'approbation (``adsengine_approve``)
    est une permission DISTINCTE, portée par les actions concernées (ENG7).
    """

    read_permission = 'adsengine_view'
    write_permission = 'adsengine_manage'


class MetaConnectionViewSet(AdsengineViewSet):
    """ENG2 — CRUD de la connexion Meta (une par société).

    ``credentials`` est write-only (jamais relu) ; ``company`` est posée côté
    serveur. Aucun secret ne fuit dans une réponse GET.
    """

    queryset = MetaConnection.objects.all()
    serializer_class = MetaConnectionSerializer
