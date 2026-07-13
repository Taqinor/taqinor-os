from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    IpAllowRuleViewSet,
    LoginBannerView,
    NetworkPolicyViewSet,
    TrustedDeviceViewSet,
)

router = DefaultRouter()
router.register(r'network-policies', NetworkPolicyViewSet)
router.register(r'ip-allow-rules', IpAllowRuleViewSet)
router.register(r'trusted-devices', TrustedDeviceViewSet)

urlpatterns = [
    path('login-banner/', LoginBannerView.as_view(), name='identity-login-banner'),
    path('', include(router.urls)),
]
