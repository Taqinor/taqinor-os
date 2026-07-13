"""Vues d'administration de la fondation Identité & accès.

NTSEC11 — CRUD de la politique réseau (allowlist IP/CIDR), réservé au
Directeur (rôle Administrateur). Tout est scopé société côté serveur : la
société n'est jamais lue du corps de requête.
"""
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

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


class BreakGlassView(APIView):
    """NTSEC22 — octroi/liste des accès break-glass (Directeur only).

    POST ``{user_id, motif, duree_minutes}`` élève temporairement un compte de
    la société ; GET liste les octrois de la société (scopé société)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        from .models import BreakGlassGrant
        grants = BreakGlassGrant.objects.filter(
            company=request.user.company).order_by('-created_at')[:100]
        data = [{
            'id': g.id, 'user': g.user_id, 'motif': g.motif,
            'accorde_par': g.accorde_par_id,
            'active_jusqu_a': g.active_jusqu_a,
            'revoque_le': g.revoque_le, 'actif': g.est_actif,
        } for g in grants]
        return Response({'results': data})

    def post(self, request):
        from authentication.models import CustomUser

        from .breakglass import acting_user_has_mfa, grant_break_glass

        motif = (request.data.get('motif') or '').strip()
        if not motif:
            raise DRFValidationError({'motif': 'Le motif est obligatoire.'})
        # Exige une MFA active côté Directeur agissant (proxy NTSEC9).
        if not acting_user_has_mfa(request.user):
            return Response(
                {'detail': 'MFA requise pour un accès break-glass.'},
                status=403)
        try:
            duree = int(request.data.get('duree_minutes') or 60)
        except (TypeError, ValueError):
            raise DRFValidationError({'duree_minutes': 'Durée invalide.'})
        if duree <= 0 or duree > 24 * 60:
            raise DRFValidationError(
                {'duree_minutes': 'Durée hors bornes (1–1440 min).'})
        # Cible STRICTEMENT dans la société de l'appelant (jamais cross-tenant).
        target = CustomUser.objects.filter(
            pk=request.data.get('user_id'),
            company=request.user.company).first()
        if target is None:
            raise DRFValidationError({'user_id': 'Compte inconnu.'})
        grant = grant_break_glass(
            target=target, motif=motif, duree_minutes=duree,
            accorde_par=request.user)
        return Response({'id': grant.id, 'active_jusqu_a': grant.active_jusqu_a},
                        status=201)
