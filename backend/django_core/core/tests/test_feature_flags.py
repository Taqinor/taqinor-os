"""Tests FG391 — flags de modules par société.

Couvre :
  * service : activé par défaut (pas de ligne), désactivé sur ligne actif=False ;
  * modules_desactives ;
  * endpoint : écriture admin-only, lecture ouverte, company imposée, isolation.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import feature_flags
from core.models import ModuleToggle
from core.views import ModuleToggleViewSet

User = get_user_model()


class FeatureFlagServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def test_enabled_by_default(self):
        self.assertTrue(feature_flags.module_actif(self.company, 'sav'))

    def test_disabled_when_toggle_off(self):
        ModuleToggle.objects.create(
            company=self.company, module='flotte', actif=False)
        self.assertFalse(feature_flags.module_actif(self.company, 'flotte'))
        self.assertIn('flotte',
                      feature_flags.modules_desactives(self.company))

    def test_none_company_returns_default(self):
        self.assertTrue(feature_flags.module_actif(None, 'sav'))


class ModuleToggleViewSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.admin = User.objects.create_user(
            username='mt_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='mt_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_create_requires_admin_tier(self):
        req = self.factory.post(
            '/module-toggles/', {'module': 'sav', 'actif': False},
            format='json')
        force_authenticate(req, user=self.user)
        resp = ModuleToggleViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_imposes_company(self):
        req = self.factory.post(
            '/module-toggles/', {'module': 'sav', 'actif': False},
            format='json')
        force_authenticate(req, user=self.admin)
        resp = ModuleToggleViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        tog = ModuleToggle.objects.get(pk=resp.data['id'])
        self.assertEqual(tog.company, self.company)

    def test_list_company_isolation(self):
        ModuleToggle.objects.create(
            company=self.other, module='secret', actif=False)
        req = self.factory.get('/module-toggles/')
        force_authenticate(req, user=self.user)
        resp = ModuleToggleViewSet.as_view({'get': 'list'})(req)
        modules = {row['module'] for row in resp.data}
        self.assertNotIn('secret', modules)
