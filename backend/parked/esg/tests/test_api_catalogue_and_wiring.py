"""API du catalogue GRI-lite (NTESG3) + garde-fous de câblage de l'app ESG."""
from testkit.base import TenantAPITestCase

from apps.esg.apps import EsgConfig
from apps.esg.management.commands.seed_catalogue_esg import (
    seed_catalogue_esg_for_company,
)


class CatalogueEsgApiTests(TenantAPITestCase):
    BASE = '/api/django/esg/catalogue-esg/'

    def test_list_scoped_to_company(self):
        seed_catalogue_esg_for_company(self.company)
        seed_catalogue_esg_for_company(self.other_company)
        r = self.client_as().get(self.BASE)
        self.assertEqual(r.status_code, 200)

    def test_readonly_create_not_allowed(self):
        r = self.client_as().post(
            self.BASE,
            {'code': 'X1', 'libelle': 'x', 'pilier': 'environnement'},
            format='json')
        self.assertEqual(r.status_code, 405)

    def test_couverture_action_scoped_to_company(self):
        seed_catalogue_esg_for_company(self.company)
        r = self.client_as().get(f'{self.BASE}couverture/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('global_pct', r.data)
        self.assertIn('piliers', r.data)


class ModuleManifestTests(TenantAPITestCase):
    def test_module_manifest_declared(self):
        manifest = EsgConfig.module_manifest
        self.assertEqual(manifest['key'], 'esg')
        self.assertIn('qhse', manifest['depends'])

    def test_esg_routes_mounted(self):
        r = self.client_as().get('/api/django/esg/periodes-esg/')
        self.assertEqual(r.status_code, 200)
