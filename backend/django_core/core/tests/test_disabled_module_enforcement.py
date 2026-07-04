"""Tests ODX4 — enforcement 404 des modules désactivés.

Couvre :
  * le mapping préfixe d'URL → clé de module (helper) ;
  * module désactivé → 404 pour CETTE société seulement ;
  * module actif / défaut → pas de blocage (byte-identique) ;
  * exemptions (fondation, public) ;
  * isolation multi-tenant.
"""
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase

from authentication.models import Company
from core import permissions
from core.models import ModuleToggle

User = get_user_model()


class PrefixMappingTests(TestCase):
    def test_business_prefix_maps_to_module(self):
        self.assertEqual(
            permissions._module_key_for_path('/api/django/flotte/vehicules/'),
            'flotte')

    def test_prefix_alias(self):
        self.assertEqual(
            permissions._module_key_for_path('/api/django/gestion-projet/x/'),
            'gestion_projet')

    def test_exempt_prefixes_return_none(self):
        for path in ('/api/django/roles/', '/api/django/parametres/x/',
                     '/api/django/core/modules/', '/api/django/public/doc/',
                     '/api/django/reporting/kpis/', '/api/django/audit/'):
            self.assertIsNone(
                permissions._module_key_for_path(path), path)

    def test_non_api_path_returns_none(self):
        self.assertIsNone(permissions._module_key_for_path('/static/x.css'))
        self.assertIsNone(permissions._module_key_for_path('/'))


class MiddlewareEnforcementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.user = User.objects.create_user(
            username='mw_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.other_user = User.objects.create_user(
            username='mw_other', password='x', role_legacy='normal',
            company=cls.other)

    def _mw(self):
        sentinel = HttpResponse('ok')
        return permissions.DisabledModuleMiddleware(lambda req: sentinel), \
            sentinel

    def _request(self, path, user):
        from django.test import RequestFactory
        req = RequestFactory().get(path)
        req.user = user
        return req

    def test_disabled_module_returns_404(self):
        ModuleToggle.objects.create(
            company=self.company, module='flotte', actif=False)
        mw, sentinel = self._mw()
        resp = mw(self._request('/api/django/flotte/vehicules/', self.user))
        self.assertEqual(resp.status_code, 404)
        self.assertIsNot(resp, sentinel)

    def test_active_module_passes_through(self):
        mw, sentinel = self._mw()
        resp = mw(self._request('/api/django/flotte/vehicules/', self.user))
        self.assertIs(resp, sentinel)

    def test_default_no_toggle_passes_through(self):
        mw, sentinel = self._mw()
        resp = mw(self._request('/api/django/crm/leads/', self.user))
        self.assertIs(resp, sentinel)

    def test_exempt_prefix_never_blocked(self):
        # Même si on désactivait « reporting », il est exempté.
        ModuleToggle.objects.create(
            company=self.company, module='reporting', actif=False)
        mw, sentinel = self._mw()
        resp = mw(self._request('/api/django/reporting/kpis/', self.user))
        self.assertIs(resp, sentinel)

    def test_tenant_isolation(self):
        # ACME désactive flotte ; l'autre société n'est pas affectée.
        ModuleToggle.objects.create(
            company=self.company, module='flotte', actif=False)
        mw, sentinel = self._mw()
        resp_acme = mw(
            self._request('/api/django/flotte/x/', self.user))
        resp_other = mw(
            self._request('/api/django/flotte/x/', self.other_user))
        self.assertEqual(resp_acme.status_code, 404)
        self.assertIs(resp_other, sentinel)

    def test_anonymous_not_blocked(self):
        from django.contrib.auth.models import AnonymousUser
        ModuleToggle.objects.create(
            company=self.company, module='flotte', actif=False)
        mw, sentinel = self._mw()
        resp = mw(self._request('/api/django/flotte/x/', AnonymousUser()))
        # Pas de société résolue ⇒ aucun blocage (défaut actif).
        self.assertIs(resp, sentinel)
