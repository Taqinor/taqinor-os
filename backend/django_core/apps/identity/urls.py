"""Routes de la fondation identité (NTSEC).

Montées sous ``/api/django/identity/`` (voir ``erp_agentique/urls.py``).
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views_oidc, views_saml, views_scim
from .views import (
    IdentityProviderViewSet, ScimGroupMappingViewSet, ScimTokenViewSet,
)

router = DefaultRouter()
router.register(r'providers', IdentityProviderViewSet, basename='idp')
router.register(r'scim-tokens', ScimTokenViewSet, basename='scim-token')
router.register(r'scim-group-mappings', ScimGroupMappingViewSet,
                basename='scim-group-mapping')

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
    # NTSEC5 — Provisioning SCIM 2.0 — Users (jeton SCIM porteur dédié).
    path('scim/v2/<slug:company_slug>/Users', views_scim.ScimUsersView.as_view(),
         name='scim-users'),
    path('scim/v2/<slug:company_slug>/Users/<int:pk>',
         views_scim.ScimUserDetailView.as_view(), name='scim-user-detail'),
    # NTSEC6 — Provisioning SCIM 2.0 — Groups → rôles.
    path('scim/v2/<slug:company_slug>/Groups',
         views_scim.ScimGroupsView.as_view(), name='scim-groups'),
    path('scim/v2/<slug:company_slug>/Groups/<int:pk>',
         views_scim.ScimGroupDetailView.as_view(), name='scim-group-detail'),
]
