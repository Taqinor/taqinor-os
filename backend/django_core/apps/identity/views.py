"""Vues d'administration de la fondation Identité & accès.

NTSEC11 — CRUD de la politique réseau (allowlist IP/CIDR), réservé au
Directeur (rôle Administrateur). Tout est scopé société côté serveur : la
société n'est jamais lue du corps de requête.
"""
from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError

from authentication.permissions import IsAdminRole
from core.mixins import TenantMixin
from core.viewsets import CompanyScopedModelViewSet

from .models import IpAllowRule, NetworkPolicy, TrustedDevice
from .serializers import (
    IpAllowRuleSerializer,
    NetworkPolicySerializer,
    TrustedDeviceSerializer,
)


class NetworkPolicyViewSet(CompanyScopedModelViewSet):
    """Politique réseau de la société (une seule par société)."""

    queryset = NetworkPolicy.objects.all().prefetch_related('rules')
    serializer_class = NetworkPolicySerializer
    permission_classes = [IsAdminRole]

    def perform_create(self, serializer):
        company = self.request.user.company
        if NetworkPolicy.objects.filter(company=company).exists():
            raise DRFValidationError(
                'Une politique réseau existe déjà pour cette société.')
        serializer.save(company=company)


class IpAllowRuleViewSet(CompanyScopedModelViewSet):
    """Plages CIDR autorisées, rattachées à la politique de la société."""

    queryset = IpAllowRule.objects.all()
    serializer_class = IpAllowRuleSerializer
    permission_classes = [IsAdminRole]

    def perform_create(self, serializer):
        company = self.request.user.company
        policy = serializer.validated_data.get('policy')
        # La politique référencée doit appartenir à la société de l'appelant
        # (jamais rattacher une règle à la politique d'un autre tenant).
        if policy is None or policy.company_id != company.id:
            raise DRFValidationError(
                {'policy': 'Politique inconnue pour votre société.'})
        serializer.save(company=company)


class TrustedDeviceViewSet(TenantMixin,
                           mixins.ListModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet):
    """NTSEC14 — appareils de confiance de l'utilisateur connecté (list + révoquer).

    Chaque utilisateur ne voit et ne révoque QUE ses propres appareils (jamais
    ceux d'un autre compte), en plus du scope société hérité de ``TenantMixin``.
    La révocation est une révocation DOUCE (``revoque_le``) qui reforce
    immédiatement la MFA sur cet appareil — la trace reste en base.
    """

    queryset = TrustedDevice.objects.all()
    serializer_class = TrustedDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Scope société (TenantMixin) PUIS restriction au compte appelant.
        return (
            super().get_queryset()
            .filter(user=self.request.user, revoque_le__isnull=True)
        )

    def perform_destroy(self, instance):
        from django.utils import timezone
        instance.revoque_le = timezone.now()
        instance.save(update_fields=['revoque_le'])
