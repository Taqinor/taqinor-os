"""Routes de la fondation identité (NTSEC).

Montées sous ``/api/django/identity/`` (voir ``erp_agentique/urls.py``).
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IdentityProviderViewSet

router = DefaultRouter()
router.register(r'providers', IdentityProviderViewSet, basename='idp')

urlpatterns = [
    path('', include(router.urls)),
]
