from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    IpAllowRuleViewSet,
    NetworkPolicyViewSet,
    TrustedDeviceViewSet,
)

router = DefaultRouter()
router.register(r'network-policies', NetworkPolicyViewSet)
router.register(r'ip-allow-rules', IpAllowRuleViewSet)
router.register(r'trusted-devices', TrustedDeviceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
