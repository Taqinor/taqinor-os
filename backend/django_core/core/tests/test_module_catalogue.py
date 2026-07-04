"""Tests ODX3 — catalogue de modules + fermeture de dépendances.

Couvre :
  * le catalogue reflète manifest + état par société (défaut actif) ;
  * activer un module réactive ses dépendances (fermeture) ;
  * désactiver un module dont un module actif dépend → 400 (sauf cascade) ;
  * cascade désactive aussi les dépendants ;
  * lecture ouverte / écriture admin-only ;
  * isolation multi-tenant (aucune fuite inter-sociétés).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import feature_flags
from core.models import ModuleToggle
from core.views import ModuleCatalogViewSet

User = get_user_model()


class CatalogueServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def test_catalogue_default_all_active(self):
        cat = feature_flags.catalogue_modules(self.company)
        keys = {row['key'] for row in cat}
        # Modules installables présents, fondation absente (installable=False).
        self.assertIn('stock', keys)
        self.assertIn('ventes', keys)
        self.assertNotIn('core', keys)
        self.assertNotIn('roles', keys)
        for row in cat:
            self.assertTrue(row['actif'])

    def test_catalogue_reflects_toggle(self):
        ModuleToggle.objects.create(
            company=self.company, module='flotte', actif=False)
        cat = {row['key']: row['actif']
               for row in feature_flags.catalogue_modules(self.company)}
        self.assertFalse(cat['flotte'])
        self.assertTrue(cat['stock'])

    def test_activer_reactivates_dependencies(self):
        # ventes dépend de crm ; désactiver les deux puis activer ventes.
        ModuleToggle.objects.create(
            company=self.company, module='crm', actif=False)
        ModuleToggle.objects.create(
            company=self.company, module='ventes', actif=False)
        feature_flags.activer_module(self.company, 'ventes')
        self.assertTrue(feature_flags.module_actif(self.company, 'ventes'))
        self.assertTrue(feature_flags.module_actif(self.company, 'crm'))

    def test_desactiver_with_active_dependent_raises(self):
        # crm est requis par ventes/sav/litiges (actifs par défaut).
        with self.assertRaises(feature_flags.DependencyError) as ctx:
            feature_flags.desactiver_module(self.company, 'crm')
        self.assertTrue(ctx.exception.dependents)

    def test_desactiver_cascade(self):
        feature_flags.desactiver_module(self.company, 'crm', cascade=True)
        self.assertFalse(feature_flags.module_actif(self.company, 'crm'))
        # ventes dépend de crm → désactivé aussi.
        self.assertFalse(feature_flags.module_actif(self.company, 'ventes'))

    def test_desactiver_leaf_module(self):
        # pos dépend de stock mais rien ne dépend de pos → OK.
        feature_flags.desactiver_module(self.company, 'pos')
        self.assertFalse(feature_flags.module_actif(self.company, 'pos'))
        self.assertTrue(feature_flags.module_actif(self.company, 'stock'))

    def test_unknown_module_raises(self):
        with self.assertRaises(feature_flags.DependencyError):
            feature_flags.activer_module(self.company, 'nexistepas')


class CatalogueEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')
        cls.admin = User.objects.create_user(
            username='mc_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='mc_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def _list(self, user):
        req = self.factory.get('/modules/')
        force_authenticate(req, user=user)
        return ModuleCatalogViewSet.as_view({'get': 'list'})(req)

    def test_list_open_to_authenticated(self):
        resp = self._list(self.user)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(any(r['key'] == 'stock' for r in resp.data))

    def test_desactiver_requires_admin(self):
        req = self.factory.post('/modules/pos/desactiver/')
        force_authenticate(req, user=self.user)
        resp = ModuleCatalogViewSet.as_view(
            {'post': 'desactiver'})(req, pk='pos')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_desactiver_with_dependent_returns_400(self):
        req = self.factory.post('/modules/crm/desactiver/')
        force_authenticate(req, user=self.admin)
        resp = ModuleCatalogViewSet.as_view(
            {'post': 'desactiver'})(req, pk='crm')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('dependants', resp.data)

    def test_desactiver_cascade_query_param(self):
        req = self.factory.post('/modules/crm/desactiver/?cascade=1')
        force_authenticate(req, user=self.admin)
        resp = ModuleCatalogViewSet.as_view(
            {'post': 'desactiver'})(req, pk='crm')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('crm', resp.data['desactives'])

    def test_activer_endpoint(self):
        ModuleToggle.objects.create(
            company=self.company, module='pos', actif=False)
        req = self.factory.post('/modules/pos/activer/')
        force_authenticate(req, user=self.admin)
        resp = ModuleCatalogViewSet.as_view(
            {'post': 'activer'})(req, pk='pos')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(feature_flags.module_actif(self.company, 'pos'))

    def test_tenant_isolation(self):
        # Désactiver pos pour ACME ne touche pas Autre.
        feature_flags.desactiver_module(self.company, 'pos')
        self.assertFalse(feature_flags.module_actif(self.company, 'pos'))
        self.assertTrue(feature_flags.module_actif(self.other, 'pos'))
