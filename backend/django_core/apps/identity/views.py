"""Vues d'administration de la fondation Identité & accès.

NTSEC11 — CRUD de la politique réseau (allowlist IP/CIDR), réservé au
Directeur (rôle Administrateur). Tout est scopé société côté serveur : la
société n'est jamais lue du corps de requête.
"""
from rest_framework.exceptions import ValidationError as DRFValidationError

from authentication.permissions import IsAdminRole
from core.viewsets import CompanyScopedModelViewSet

from .models import IdentityProvider, IpAllowRule, NetworkPolicy
from .serializers import (
    IdentityProviderSerializer,
    IpAllowRuleSerializer,
    NetworkPolicySerializer,
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


class IdentityProviderViewSet(CompanyScopedModelViewSet):
    """CRUD des fournisseurs d'identité SSO de la société (NTSEC1).

    Réservé au Directeur (rôle Administrateur). La société est forcée côté
    serveur ; l'activation d'un second IdP du même protocole est refusée (400)
    plutôt que de laisser remonter une IntegrityError.
    """

    queryset = IdentityProvider.objects.all()
    serializer_class = IdentityProviderSerializer
    permission_classes = [IsAdminRole]

    def _reject_double_active(self, company, protocol, actif, exclude_pk=None):
        if not actif:
            return
        qs = IdentityProvider.objects.filter(
            company=company, protocol=protocol, actif=True)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            raise DRFValidationError(
                {'actif': 'Un fournisseur %s actif existe déjà pour cette '
                          'société.' % protocol})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._reject_double_active(
            company,
            serializer.validated_data.get('protocol'),
            serializer.validated_data.get('actif', False),
        )
        serializer.save(company=company)

    def perform_update(self, serializer):
        company = self.request.user.company
        instance = serializer.instance
        self._reject_double_active(
            company,
            serializer.validated_data.get('protocol', instance.protocol),
            serializer.validated_data.get('actif', instance.actif),
            exclude_pk=instance.pk,
        )
        serializer.save(company=company)
