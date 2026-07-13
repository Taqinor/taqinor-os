from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    IdentityProviderViewSet,
    IpAllowRuleViewSet,
    NetworkPolicyViewSet,
)

router = DefaultRouter()
router.register(r'network-policies', NetworkPolicyViewSet)
router.register(r'ip-allow-rules', IpAllowRuleViewSet)
router.register(r'providers', IdentityProviderViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
