"""Vues d'administration de la fondation identité (NTSEC).

``IdentityProviderViewSet`` (NTSEC1) — CRUD des IdP SSO d'une société, réservé
au Directeur/Administrateur (``IsAdminRole``). Multi-tenant strict : le
queryset est filtré par ``request.user.company`` et ``company`` est forcé côté
serveur à la création (jamais accepté depuis le corps).
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAdminRole

from .models import IdentityProvider, ScimGroupMapping, ScimToken
from .serializers import (
    IdentityProviderSerializer, ScimGroupMappingSerializer, ScimTokenSerializer,
)


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


class ScimTokenViewSet(viewsets.ModelViewSet):
    """Gestion des jetons SCIM d'une société (NTSEC5, Directeur/Admin only).

    Le secret en clair n'est renvoyé qu'à la création/rotation, jamais relu.
    """

    serializer_class = ScimTokenSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if company is None:
            return ScimToken.objects.none()
        return ScimToken.objects.filter(company=company)

    def create(self, request, *args, **kwargs):
        label = (request.data.get('label') or '')[:120]
        token, raw = ScimToken.issue(
            company=request.user.company, label=label,
            created_by=request.user)
        data = ScimTokenSerializer(token).data
        # Secret montré UNE seule fois, à la création.
        data['token'] = raw
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """NTSEC29 — rotation : invalide l'ancien secret, en émet un nouveau."""
        from django.utils import timezone

        from .models import generate_scim_token, hash_scim_token
        token = self.get_object()
        raw = generate_scim_token()
        token.token_hash = hash_scim_token(raw)
        token.prefix = raw[:12]
        token.last_rotated_at = timezone.now()
        token.actif = True
        token.save(update_fields=[
            'token_hash', 'prefix', 'last_rotated_at', 'actif'])
        data = ScimTokenSerializer(token).data
        data['token'] = raw
        return Response(data)


class ScimGroupMappingViewSet(viewsets.ModelViewSet):
    """CRUD des mappings groupe SCIM → rôle (NTSEC6, Directeur/Admin only)."""

    serializer_class = ScimGroupMappingSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if company is None:
            return ScimGroupMapping.objects.none()
        return ScimGroupMapping.objects.filter(company=company)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        serializer.save(company=self.request.user.company)
