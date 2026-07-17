"""NTPRT5 — Tests d'enforcement du portail externe.

Couvre, en miroir :

1. ``IsPortalScopedUser`` (garde des routes ``/api/django/portail/*``) :
   accorde chacune des 3 portées portail, refuse l'interne et l'anonyme.
2. Les helpers de scoping (``portal_scope_id`` / ``scope_filter_kwargs``).
3. Le refus SYMÉTRIQUE : un compte portail qui vise une route INTERNE reçoit
   403 — couverture 3 portées × 5 endpoints internes représentatifs — tandis
   que les endpoints communs essentiels (``auth/me``) restent joignables.
4. Les gardes internes transverses (``ScopedPermission`` / ``IsAnyRole``)
   excluent désormais un compte portail mais laissent passer l'interne.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.permissions import ScopedPermission
from apps.roles.models import Role, ALL_PERMISSIONS
from apps.roles.permissions import (
    IsPortalScopedUser,
    is_portal_user,
    portal_scope_id,
    scope_filter_kwargs,
)

User = get_user_model()

# 5 endpoints INTERNES représentatifs (gardés par ScopedPermission défaut ou
# IsAnyRole) — un compte portail doit recevoir 403 sur chacun.
INTERNAL_ENDPOINTS = [
    '/api/django/crm/leads/',
    '/api/django/crm/clients/',
    '/api/django/ventes/devis/',
    '/api/django/stock/produits/',
    '/api/django/reporting/saved-reports/',
]


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Portail Co', slug='portail-co')
        # Rôles système portail (permissions portail-seules, aucune interne).
        self.role_client = Role.objects.create(
            company=self.company, nom='Portail client',
            permissions=['portail_client_acces'], est_systeme=True,
        )
        self.role_fourn = Role.objects.create(
            company=self.company, nom='Portail fournisseur',
            permissions=['portail_fournisseur_acces'], est_systeme=True,
        )
        self.role_part = Role.objects.create(
            company=self.company, nom='Portail partenaire',
            permissions=['portail_partenaire_acces'], est_systeme=True,
        )
        self.u_client = User.objects.create_user(
            username='client@x.ma', password='x', company=self.company,
            role=self.role_client, portee='portail_client',
            portail_client_id=42,
        )
        self.u_fourn = User.objects.create_user(
            username='fourn@x.ma', password='x', company=self.company,
            role=self.role_fourn, portee='portail_fournisseur',
            portail_fournisseur_id=77,
        )
        self.u_part = User.objects.create_user(
            username='part@x.ma', password='x', company=self.company,
            role=self.role_part, portee='portail_partenaire',
            portail_partenaire_id=99,
        )
        # Collaborateur INTERNE (comportement inchangé).
        self.role_admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True,
        )
        self.u_interne = User.objects.create_user(
            username='interne', password='x', company=self.company,
            role=self.role_admin, role_legacy='admin',
        )
        self.portal_users = [self.u_client, self.u_fourn, self.u_part]

    def _client_for(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api


class IsPortalScopedUserTests(_Base):
    def test_grants_each_portal_scope(self):
        factory = APIRequestFactory()
        perm = IsPortalScopedUser()
        for user in self.portal_users:
            request = factory.get('/api/django/portail/x/')
            request.user = user
            self.assertTrue(
                perm.has_permission(request, None),
                f'{user.portee} devrait être autorisé sur une route portail',
            )

    def test_denies_internal_user(self):
        factory = APIRequestFactory()
        request = factory.get('/api/django/portail/x/')
        request.user = self.u_interne
        self.assertFalse(IsPortalScopedUser().has_permission(request, None))

    def test_denies_anonymous(self):
        factory = APIRequestFactory()
        request = factory.get('/api/django/portail/x/')
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        self.assertFalse(IsPortalScopedUser().has_permission(request, None))


class ScopeHelperTests(_Base):
    def test_is_portal_user(self):
        self.assertTrue(is_portal_user(self.u_client))
        self.assertFalse(is_portal_user(self.u_interne))

    def test_portal_scope_id_per_scope(self):
        self.assertEqual(portal_scope_id(self.u_client), 42)
        self.assertEqual(portal_scope_id(self.u_fourn), 77)
        self.assertEqual(portal_scope_id(self.u_part), 99)
        self.assertIsNone(portal_scope_id(self.u_interne))

    def test_portal_scope_id_none_when_unlinked(self):
        self.u_client.portail_client_id = None
        self.assertIsNone(portal_scope_id(self.u_client))

    def test_scope_filter_kwargs(self):
        self.assertEqual(
            scope_filter_kwargs(self.u_client), {'portail_client_id': 42})
        self.assertEqual(
            scope_filter_kwargs(self.u_fourn), {'portail_fournisseur_id': 77})
        self.assertIsNone(scope_filter_kwargs(self.u_interne))


class InternalGateExcludesPortalTests(_Base):
    """Les gardes transverses internes refusent un compte portail (unitaire)."""

    def _req(self, user, method='get'):
        factory = APIRequestFactory()
        request = getattr(factory, method)('/api/django/crm/leads/')
        request.user = user
        return request

    def test_is_any_role_denies_portal_allows_internal(self):
        perm = IsAnyRole()
        for user in self.portal_users:
            self.assertFalse(perm.has_permission(self._req(user), None))
        self.assertTrue(perm.has_permission(self._req(self.u_interne), None))

    def test_scoped_permission_denies_portal_allows_internal(self):
        perm = ScopedPermission()
        # Vue sans read_permission → « authentifié suffit » côté interne, mais
        # un compte portail est désormais refusé.
        view = type('V', (), {'read_permission': None, 'write_permission': None})()
        for user in self.portal_users:
            self.assertFalse(perm.has_permission(self._req(user), view))
        self.assertTrue(perm.has_permission(self._req(self.u_interne), view))

    def test_is_responsable_denies_portal(self):
        # Déjà vrai par NTPRT1 (permissions portail non « write ») — verrouillé.
        perm = IsResponsableOrAdmin()
        for user in self.portal_users:
            self.assertFalse(perm.has_permission(self._req(user), None))


class PortalUserForbiddenOnInternalRoutesTests(_Base):
    """Intégration : 3 portées × 5 endpoints internes → 403 ; auth/me joignable."""

    def test_portal_users_get_403_on_internal_endpoints(self):
        for user in self.portal_users:
            api = self._client_for(user)
            for url in INTERNAL_ENDPOINTS:
                resp = api.get(url)
                self.assertEqual(
                    resp.status_code, 403,
                    f'{user.portee} → {url} attendu 403, obtenu '
                    f'{resp.status_code}',
                )

    def test_portal_user_can_reach_common_auth_me(self):
        # L'endpoint essentiel commun (IsAuthenticated) reste joignable — la
        # frontière ne verrouille pas un compte portail hors de son propre
        # profil/déconnexion.
        api = self._client_for(self.u_client)
        resp = api.get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200)
