"""NTAPI27 — bac à sable API : reset des données de démo (clé `test` seule).

Distinct des viewsets lecture/écriture ordinaires : cette action agit sur la
SOCIÉTÉ-JUMELLE sandbox de la clé appelante (jamais la société réelle — une
clé `environnement='live'` n'a d'ailleurs aucun moyen d'atteindre ce
endpoint, voir ``IsTestApiKey``).
"""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ApiKeyAuthentication, ApiKeyRateThrottle
from .constants import ENV_TEST
from .models import ApiKey
from .public_response import PublicApiResponseMixin


class IsTestApiKey(permissions.BasePermission):
    """NTAPI26/27 — réservé aux clés `environnement='test'` (403 sinon)."""
    message = "Cette action est réservée aux clés API en environnement « test »."

    def has_permission(self, request, view):
        api_key = getattr(request, 'auth', None)
        return isinstance(api_key, ApiKey) and api_key.environnement == ENV_TEST


class SandboxResetView(PublicApiResponseMixin, APIView):
    """``POST /api/public/sandbox/reset/`` — remet le bac à sable de la clé
    appelante à son état initial (efface puis reseed les données de démo).
    Une clé `live` reçoit 403 — elle n'a jamais accès au bac à sable."""
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsTestApiKey]
    throttle_classes = [ApiKeyRateThrottle]

    def post(self, request):
        from .models import SandboxTenant
        from .services import reset_sandbox

        sandbox_company = request.auth.company
        tenant = SandboxTenant.objects.filter(
            sandbox_company=sandbox_company).first()
        if tenant is None:
            return Response(
                {'detail': 'Bac à sable introuvable pour cette clé.'},
                status=status.HTTP_404_NOT_FOUND)
        created = reset_sandbox(tenant)
        return Response({'reset': True, 'leads_recrees': created})
