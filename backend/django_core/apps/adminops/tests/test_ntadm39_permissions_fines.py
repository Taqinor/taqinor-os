"""NTADM39 — permissions fines adminops (sandbox/config-package/licences).

Un rôle CUSTOM (``est_systeme=False``) sans le code précis reçoit 403 ; un
rôle SYSTÈME (``est_systeme=True``) et un compte hérité (sans Role fin)
gardent leur comportement actuel (rétrocompat — bug-class #25 : le contrôle
est un appel EXPLICITE dans le corps de chaque action, jamais un
``get_permissions()`` qui écraserait les ``permission_classes`` par @action)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()


def _company(nom='NTADM39Co'):
    return Company.objects.create(nom=nom)


def _user_avec_role(company, username, permissions, est_systeme):
    role = Role.objects.create(
        company=company, nom=f'role-{username}',
        permissions=permissions, est_systeme=est_systeme)
    return User.objects.create_user(
        username=username, password='pw', company=company, role=role)


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


class SandboxCreerPermissionTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_role_custom_sans_le_code_refuse(self):
        user = _user_avec_role(
            self.company, 'custom-sans-code', ['roles_gerer'], est_systeme=False)
        resp = _client(user).post('/api/django/adminops/sandbox/creer/')
        self.assertEqual(resp.status_code, 403)

    def test_role_custom_avec_le_code_autorise(self):
        user = _user_avec_role(
            self.company, 'custom-avec-code',
            ['roles_gerer', 'adminops_sandbox_creer'], est_systeme=False)
        resp = _client(user).post('/api/django/adminops/sandbox/creer/')
        self.assertEqual(resp.status_code, 201)

    def test_role_systeme_sans_le_code_inchange(self):
        """Rétrocompat : un rôle SYSTÈME (Administrateur, Directeur…) garde
        l'accès même sans le code fin explicite."""
        user = _user_avec_role(
            self.company, 'systeme-sans-code', ['roles_gerer'], est_systeme=True)
        resp = _client(user).post('/api/django/adminops/sandbox/creer/')
        self.assertEqual(resp.status_code, 201)

    def test_compte_legacy_sans_role_fin_inchange(self):
        """Rétrocompat : un compte hérité (role_legacy seul, sans Role fin)
        garde son comportement actuel."""
        user = User.objects.create_user(
            username='legacy-admin', password='pw', company=self.company,
            role_legacy='admin', is_staff=True)
        resp = _client(user).post('/api/django/adminops/sandbox/creer/')
        self.assertEqual(resp.status_code, 201)


class ConfigPackagePermissionTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_exporter_refuse_sans_le_code(self):
        user = _user_avec_role(
            self.company, 'exp-sans-code', ['roles_gerer'], est_systeme=False)
        resp = _client(user).post(
            '/api/django/adminops/config-packages/exporter/',
            {'nom': 'Config'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_exporter_autorise_avec_le_code(self):
        user = _user_avec_role(
            self.company, 'exp-avec-code',
            ['roles_gerer', 'adminops_config_package_exporter'], est_systeme=False)
        resp = _client(user).post(
            '/api/django/adminops/config-packages/exporter/',
            {'nom': 'Config'}, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_appliquer_refuse_sans_le_code(self):
        user = _user_avec_role(
            self.company, 'imp-sans-code', ['roles_gerer'], est_systeme=False)
        resp = _client(user).post(
            '/api/django/adminops/config-packages/appliquer/',
            {'contenu': {}}, format='json')
        self.assertEqual(resp.status_code, 403)


class LicencesVoirPermissionTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_refuse_sans_le_code(self):
        user = _user_avec_role(
            self.company, 'lic-sans-code', ['roles_gerer'], est_systeme=False)
        resp = _client(user).get('/api/django/adminops/licences/')
        self.assertEqual(resp.status_code, 403)

    def test_autorise_avec_le_code(self):
        user = _user_avec_role(
            self.company, 'lic-avec-code',
            ['roles_gerer', 'adminops_licences_voir'], est_systeme=False)
        resp = _client(user).get('/api/django/adminops/licences/')
        self.assertEqual(resp.status_code, 200)
