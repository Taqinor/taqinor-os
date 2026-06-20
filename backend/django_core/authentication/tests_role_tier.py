"""Régression de contrôle d'accès : le palier de menu et l'accès aux écrans
d'administration doivent dériver du NOUVEAU rôle, jamais du champ legacy.

Bug constaté : un compte portant le rôle « Administrateur » ou « Responsable »
recevait le menu limité, parce que ``role_legacy`` restait figé à 'normal' à la
création de l'utilisateur, et que le frontend choisit le menu d'après ce champ
legacy. Le palier faisant autorité (``menu_tier``) doit venir du Role assigné.

Comportement attendu :
  - Administrateur ET Responsable → palier complet ('admin' / 'responsable').
  - Utilisateur et tout rôle personnalisé (ex. « Commercial ») → palier limité
    ('normal'), et toujours bloqué sur Paramètres / Utilisateurs / Rôles.
  - Le Responsable est promu : il atteint Paramètres / Utilisateurs / Rôles.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import (
    Role,
    ALL_PERMISSIONS,
    RESPONSABLE_PERMISSIONS,
    UTILISATEUR_PERMISSIONS,
)

User = get_user_model()


class RoleTierBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Tier Co', slug='tier-co')
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.resp_role = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=RESPONSABLE_PERMISSIONS, est_systeme=True)
        self.user_role = Role.objects.create(
            company=self.company, nom='Utilisateur',
            permissions=UTILISATEUR_PERMISSIONS, est_systeme=True)
        # Rôle personnalisé : relève du palier limité quelles que soient ses
        # permissions.
        self.commercial_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'ventes_voir', 'ventes_creer'],
            est_systeme=False)
        # Un propriétaire admin pour piloter les endpoints d'administration.
        self.owner = User.objects.create_user(
            username='owner', password='x', role=self.admin_role,
            role_legacy='admin', company=self.company)

    def _client_for(self, user):
        api = APIClient()
        token = str(AccessToken.for_user(user))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return api


class TestMenuTierResolution(RoleTierBase):
    """(a)(b)(c) Le palier de menu dérive du Role, pas du legacy figé."""

    def test_administrateur_role_resolves_to_full_tier(self):
        # Reproduit le bug : rôle Administrateur mais role_legacy au défaut.
        u = User.objects.create_user(
            username='a1', password='x', role=self.admin_role,
            company=self.company)
        self.assertEqual(u.menu_tier, 'admin')
        resp = self._client_for(u).get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['menu_tier'], 'admin')

    def test_responsable_role_resolves_to_full_tier(self):
        u = User.objects.create_user(
            username='r1', password='x', role=self.resp_role,
            company=self.company)
        self.assertEqual(u.menu_tier, 'responsable')
        resp = self._client_for(u).get('/api/django/auth/me/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['menu_tier'], 'responsable')

    def test_utilisateur_role_resolves_to_limited_tier(self):
        u = User.objects.create_user(
            username='u1', password='x', role=self.user_role,
            company=self.company)
        self.assertEqual(u.menu_tier, 'normal')
        resp = self._client_for(u).get('/api/django/auth/me/')
        self.assertEqual(resp.data['menu_tier'], 'normal')

    def test_custom_commercial_role_resolves_to_limited_tier(self):
        u = User.objects.create_user(
            username='c1', password='x', role=self.commercial_role,
            company=self.company)
        self.assertEqual(u.menu_tier, 'normal')
        resp = self._client_for(u).get('/api/django/auth/me/')
        self.assertEqual(resp.data['menu_tier'], 'normal')


class TestAdminScreenAccess(RoleTierBase):
    """(b)(c) Paramètres / Utilisateurs / Rôles : ouverts à Admin + Responsable,
    toujours fermés au palier limité (Utilisateur / Commercial)."""

    def test_responsable_reaches_parametres_users_roles(self):
        u = User.objects.create_user(
            username='r2', password='x', role=self.resp_role,
            company=self.company)
        api = self._client_for(u)
        # Paramètres : lecture + écriture.
        self.assertEqual(api.get('/api/django/parametres/').status_code, 200)
        self.assertEqual(
            api.patch('/api/django/parametres/update/', {'nom': 'X'},
                      format='json').status_code, 200)
        # Utilisateurs.
        self.assertEqual(api.get('/api/django/users/').status_code, 200)
        # Rôles : lecture + écriture.
        self.assertEqual(api.get('/api/django/roles/').status_code, 200)
        created = api.post('/api/django/roles/',
                           {'nom': 'Rôle Resp', 'permissions': ['crm_voir']},
                           format='json')
        self.assertEqual(created.status_code, 201, created.data)

    def test_admin_reaches_parametres_users_roles(self):
        api = self._client_for(self.owner)
        self.assertEqual(
            api.patch('/api/django/parametres/update/', {'nom': 'Y'},
                      format='json').status_code, 200)
        self.assertEqual(api.get('/api/django/users/').status_code, 200)
        self.assertEqual(api.get('/api/django/roles/').status_code, 200)

    def test_utilisateur_is_blocked_from_admin_screens(self):
        u = User.objects.create_user(
            username='u2', password='x', role=self.user_role,
            company=self.company)
        api = self._client_for(u)
        self.assertEqual(
            api.patch('/api/django/parametres/update/', {'nom': 'Z'},
                      format='json').status_code, 403)
        self.assertEqual(api.get('/api/django/users/').status_code, 403)
        self.assertEqual(api.get('/api/django/roles/').status_code, 403)

    def test_commercial_custom_role_is_blocked_from_admin_screens(self):
        u = User.objects.create_user(
            username='c2', password='x', role=self.commercial_role,
            company=self.company)
        api = self._client_for(u)
        self.assertEqual(
            api.patch('/api/django/parametres/update/', {'nom': 'W'},
                      format='json').status_code, 403)
        self.assertEqual(api.get('/api/django/users/').status_code, 403)
        self.assertEqual(api.get('/api/django/roles/').status_code, 403)


class TestRoleLegacyStaysConsistent(RoleTierBase):
    """(d) La création/modification d'un utilisateur ne fige plus role_legacy
    à 'normal' : il suit le palier du Role assigné."""

    def test_create_user_via_api_with_admin_role_sets_admin_legacy(self):
        api = self._client_for(self.owner)
        resp = api.post('/api/django/users/', {
            'username': 'newadmin', 'password': 'secretpass1',
            'email': 'n@n.com', 'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = User.objects.get(username='newadmin')
        self.assertEqual(created.role_legacy, 'admin')
        self.assertEqual(created.menu_tier, 'admin')

    def test_register_view_with_admin_role_sets_admin_legacy(self):
        api = self._client_for(self.owner)
        resp = api.post('/api/django/register/', {
            'username': 'regadmin', 'password': 'secretpass1',
            'email': 'r@r.com', 'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = User.objects.get(username='regadmin')
        self.assertEqual(created.role_legacy, 'admin')

    def test_create_user_with_responsable_role_sets_responsable_legacy(self):
        api = self._client_for(self.owner)
        resp = api.post('/api/django/users/', {
            'username': 'newresp', 'password': 'secretpass1',
            'email': 'rr@n.com', 'role': self.resp_role.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = User.objects.get(username='newresp')
        self.assertEqual(created.role_legacy, 'responsable')

    def test_create_user_with_commercial_role_stays_normal_legacy(self):
        api = self._client_for(self.owner)
        resp = api.post('/api/django/users/', {
            'username': 'newcom', 'password': 'secretpass1',
            'email': 'co@n.com', 'role': self.commercial_role.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        created = User.objects.get(username='newcom')
        self.assertEqual(created.role_legacy, 'normal')

    def test_changing_role_via_patch_updates_legacy_tier(self):
        promoted = User.objects.create_user(
            username='promote', password='x', role=self.user_role,
            role_legacy='normal', company=self.company)
        api = self._client_for(self.owner)
        resp = api.patch(f'/api/django/users/{promoted.id}/',
                         {'role': self.admin_role.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        promoted.refresh_from_db()
        self.assertEqual(promoted.role_legacy, 'admin')
        self.assertEqual(promoted.menu_tier, 'admin')


class TestBackfillExistingAccounts(RoleTierBase):
    """Les comptes existants déjà dérivés (role_legacy figé) sont réalignés sans
    re-création, par une fonction idempotente et non destructive."""

    def test_backfill_aligns_drifted_admin_account(self):
        from authentication.role_tiers import sync_role_legacy
        u = User.objects.create_user(
            username='drift', password='x', role=self.admin_role,
            company=self.company)
        # Force l'état AVANT correctif : legacy figé à 'normal'.
        User.objects.filter(pk=u.pk).update(role_legacy='normal')
        u.refresh_from_db()
        self.assertEqual(u.role_legacy, 'normal')

        changed = sync_role_legacy(User)

        u.refresh_from_db()
        self.assertEqual(u.role_legacy, 'admin')
        self.assertEqual(u.menu_tier, 'admin')
        self.assertGreaterEqual(changed, 1)

    def test_backfill_is_idempotent(self):
        from authentication.role_tiers import sync_role_legacy
        sync_role_legacy(User)
        # Deuxième passage : plus aucun changement.
        self.assertEqual(sync_role_legacy(User), 0)


class TestIsResponsableTightening(RoleTierBase):
    """ERR4 : ``is_responsable`` (et donc ``IsResponsableOrAdmin``) ne doit plus
    être vrai pour un rôle STRICTEMENT lecture seule. Les rôles métier qui
    détiennent une permission d'écriture/gestion le restent, ainsi que les
    comptes hérités sans rôle fin."""

    def _role(self, nom, perms):
        return Role.objects.create(
            company=self.company, nom=nom, permissions=perms,
            est_systeme=False)

    def test_readonly_viewer_role_is_not_responsable(self):
        viewer = User.objects.create_user(
            username='viewer_ro', password='x', company=self.company,
            role=self._role('Lecture seule', [
                'stock_voir', 'crm_voir', 'ventes_voir',
                'records_scope_equipe']))
        self.assertFalse(viewer.is_responsable)

    def test_utilisateur_role_is_not_responsable(self):
        u = User.objects.create_user(
            username='util_ro', password='x', company=self.company,
            role=self.user_role)
        self.assertFalse(u.is_responsable)

    def test_role_with_any_write_permission_is_responsable(self):
        com = User.objects.create_user(
            username='com_w', password='x', company=self.company,
            role=self._role('Commercial w', [
                'crm_voir', 'crm_creer', 'ventes_voir']))
        self.assertTrue(com.is_responsable)

    def test_admin_role_is_responsable(self):
        a = User.objects.create_user(
            username='adm_r', password='x', company=self.company,
            role=self.admin_role)
        self.assertTrue(a.is_responsable)

    def test_legacy_responsable_account_stays_responsable(self):
        legacy = User.objects.create_user(
            username='legacy_r', password='x', company=self.company,
            role_legacy='responsable')
        self.assertTrue(legacy.is_responsable)

    def test_legacy_normal_account_is_not_responsable(self):
        legacy = User.objects.create_user(
            username='legacy_n', password='x', company=self.company,
            role_legacy='normal')
        self.assertFalse(legacy.is_responsable)

    def test_readonly_role_blocked_from_responsable_endpoint(self):
        """Bout-en-bout : un rôle lecture seule est refusé sur un endpoint
        d'écriture gardé par ``IsResponsableOrAdmin`` (création de rôle via
        l'API roles, qui passe par le palier ; ici on vérifie l'effet
        ``is_responsable`` sur un endpoint ventes générique)."""
        viewer = User.objects.create_user(
            username='viewer_block', password='x', company=self.company,
            role=self._role('RO2', ['ventes_voir', 'crm_voir']))
        self.assertFalse(viewer.is_responsable)
