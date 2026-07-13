"""Vues d'administration de la fondation Identité & accès.

NTSEC11 — CRUD de la politique réseau (allowlist IP/CIDR), réservé au
Directeur (rôle Administrateur). Tout est scopé société côté serveur : la
société n'est jamais lue du corps de requête.
"""
from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

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


def _client_ip(request):
    """Première IP de X-Forwarded-For (derrière proxy) sinon REMOTE_ADDR."""
    meta = getattr(request, 'META', {}) or {}
    fwd = (meta.get('HTTP_X_FORWARDED_FOR', '') or '').split(',')[0].strip()
    return fwd or meta.get('REMOTE_ADDR', '') or ''


def _banner_profile(username):
    """Profil société résolu depuis un username (pré-auth), sinon le profil par
    défaut (pk=1, convention historique) — best-effort, jamais d'exception."""
    from apps.parametres.models_company import CompanyProfile
    from authentication.models import CustomUser
    uname = (username or '').strip()
    if uname:
        user = CustomUser.objects.filter(username__iexact=uname).first()
        company = getattr(user, 'company', None) if user else None
        if company is not None:
            profile = CompanyProfile.objects.filter(company=company).first()
            if profile is not None:
                return profile, user
    # Repli : instance par défaut (déploiement mono-société / username inconnu).
    return CompanyProfile.objects.filter(pk=1).first(), None


class LoginBannerView(APIView):
    """NTSEC28 — bannière/mention légale de connexion (pré-auth, AllowAny).

    * ``GET  ?username=`` — renvoie le texte de bannière de la société de cet
      utilisateur (ou du profil par défaut). Toujours 200 ; texte vide = aucun
      bandeau (écran de login inchangé). Le texte de bannière est une mention
      légale destinée à être affichée à tout visiteur — rien de sensible.
    * ``POST {username}`` — journalise l'accusé (AuditLog best-effort, IP/UA),
      scopé à la société résolue, UNIQUEMENT si un texte de bannière est
      configuré. Sans bannière : no-op.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        username = request.query_params.get('username', '')
        profile, _ = _banner_profile(username)
        text = getattr(profile, 'login_banner_text', '') if profile else ''
        return Response({'login_banner_text': text or ''})

    def post(self, request):
        username = (request.data.get('username') if hasattr(request, 'data')
                    else None) or ''
        profile, user = _banner_profile(username)
        text = getattr(profile, 'login_banner_text', '') if profile else ''
        if not text:
            # Aucune bannière configurée → rien à acquitter (inchangé).
            return Response({'acknowledged': False})
        company = getattr(profile, 'company', None)
        try:
            from apps.audit.models import AuditLog
            from apps.audit.recorder import record
            ua = (request.META.get('HTTP_USER_AGENT', '') or '')[:300]
            record(
                AuditLog.Action.SECURITY_ALERT,
                user=user,
                company=company,
                actor_username=(username or None),
                detail=('Bannière de connexion acquittée depuis '
                        f'{_client_ip(request)} (UA: {ua}).'),
            )
        except Exception:  # noqa: BLE001 - journalisation best-effort
            pass
        return Response({'acknowledged': True})
