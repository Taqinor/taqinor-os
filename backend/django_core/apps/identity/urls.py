from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .scim import (
    ScimGroupDetailView,
    ScimGroupsView,
    ScimUserDetailView,
    ScimUsersView,
)
from .views import BreakGlassView, SecurityPostureView
from .views import (
    IdentityProviderViewSet,
    IpAllowRuleViewSet,
    LoginBannerView,
    NetworkPolicyViewSet,
    TrustedDeviceViewSet,
)
from apps.publicapi.views import ServiceAccountViewSet

router = DefaultRouter()
router.register(r'network-policies', NetworkPolicyViewSet)
router.register(r'ip-allow-rules', IpAllowRuleViewSet)
router.register(r'trusted-devices', TrustedDeviceViewSet)
router.register(r'providers', IdentityProviderViewSet)
# NTSEC24 — comptes de service (modèle dans publicapi, exposé sous identity).
router.register(r'service-accounts', ServiceAccountViewSet,
                basename='service-account')

urlpatterns = [
    path('login-banner/', LoginBannerView.as_view(), name='identity-login-banner'),
    # SCIM 2.0 — provisioning machine-à-machine (NTSEC5/6), auth par jeton SCIM.
    path('scim/v2/<slug:company_slug>/Users',
         ScimUsersView.as_view(), name='scim-users'),
    path('scim/v2/<slug:company_slug>/Users/<int:pk>',
         ScimUserDetailView.as_view(), name='scim-user-detail'),
    path('scim/v2/<slug:company_slug>/Groups',
         ScimGroupsView.as_view(), name='scim-groups'),
    path('scim/v2/<slug:company_slug>/Groups/<int:pk>',
         ScimGroupDetailView.as_view(), name='scim-group-detail'),
    # NTSEC22 — accès break-glass (Directeur only).
    path('break-glass/', BreakGlassView.as_view(), name='break-glass'),
    # NTSEC27 — posture de sécurité consolidée (Directeur only).
    path('posture/', SecurityPostureView.as_view(), name='security-posture'),
    path('', include(router.urls)),
]
