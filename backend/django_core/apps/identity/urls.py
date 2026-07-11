"""Routes de la fondation identité (NTSEC).

Montées sous ``/api/django/identity/`` (voir ``erp_agentique/urls.py``).
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views_oidc, views_saml
from .views import IdentityProviderViewSet

router = DefaultRouter()
router.register(r'providers', IdentityProviderViewSet, basename='idp')

urlpatterns = [
    path('', include(router.urls)),
    # NTSEC2 — SSO SAML 2.0 par tenant (endpoints publics, résolus par slug).
    path('saml/<slug:company_slug>/login/', views_saml.saml_login,
         name='saml-login'),
    path('saml/<slug:company_slug>/acs/', views_saml.saml_acs,
         name='saml-acs'),
    path('saml/<slug:company_slug>/metadata/', views_saml.saml_metadata,
         name='saml-metadata'),
    path('saml/<slug:company_slug>/sls/', views_saml.saml_sls,
         name='saml-sls'),
    # NTSEC3 — SSO OIDC (Authorization Code + PKCE) par tenant.
    path('oidc/<slug:company_slug>/login/', views_oidc.oidc_login,
         name='oidc-login'),
    path('oidc/<slug:company_slug>/callback/', views_oidc.oidc_callback,
         name='oidc-callback'),
]
