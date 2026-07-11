"""Vues d'administration de la fondation identité (NTSEC).

``IdentityProviderViewSet`` (NTSEC1) — CRUD des IdP SSO d'une société, réservé
au Directeur/Administrateur (``IsAdminRole``). Multi-tenant strict : le
queryset est filtré par ``request.user.company`` et ``company`` est forcé côté
serveur à la création (jamais accepté depuis le corps).
"""
from rest_framework import viewsets

from authentication.permissions import IsAdminRole

from .models import IdentityProvider
from .serializers import IdentityProviderSerializer


class IdentityProviderViewSet(viewsets.ModelViewSet):
    """CRUD des fournisseurs d'identité SSO (Directeur/Admin only)."""

    serializer_class = IdentityProviderSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if company is None:
            return IdentityProvider.objects.none()
        return IdentityProvider.objects.filter(company=company)

    def perform_create(self, serializer):
        # Société FORCÉE côté serveur — jamais depuis le corps de la requête.
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        # Ne jamais laisser une mise à jour ré-attribuer la société.
        serializer.save(company=self.request.user.company)
