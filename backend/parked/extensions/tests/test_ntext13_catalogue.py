"""NTEXT13 — registre de packages d'extension (marketplace interne).

Critère : le catalogue liste ≥1 package d'exemple (« Suivi SAV avancé »)
avec son manifest lisible, READ-ONLY, jamais lié à une société."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.extensions.models import ExtensionPackage
from authentication.models import Company

User = get_user_model()


class NTEXT13Base(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ntext13-co', defaults={'nom': 'NTEXT13 Co'})[0]
        self.user = User.objects.create_user(
            username='ntext13_user', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class TestSeedMigrationCreatesExamplePackage(TestCase):
    def test_sav_avance_seeded_globally(self):
        pkg = ExtensionPackage.objects.get(code='sav_avance')
        self.assertEqual(pkg.nom, 'Suivi SAV avancé')
        self.assertIn('custom_object_defs', pkg.manifest)


class TestCatalogueEndpoint(NTEXT13Base):
    def test_catalogue_lists_at_least_one_package(self):
        resp = self.api.get('/api/django/extensions/catalogue/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertGreaterEqual(len(rows), 1)
        codes = [r['code'] for r in rows]
        self.assertIn('sav_avance', codes)

    def test_manifest_is_readable(self):
        resp = self.api.get('/api/django/extensions/catalogue/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        pkg = next(r for r in rows if r['code'] == 'sav_avance')
        self.assertIn('custom_object_defs', pkg['manifest'])
        self.assertEqual(
            pkg['manifest']['custom_object_defs'][0]['code'],
            'intervention_sav')

    def test_catalogue_is_read_only_no_create_endpoint(self):
        resp = self.api.post('/api/django/extensions/catalogue/', {
            'code': 'nouveau', 'nom': 'Nouveau package',
        }, format='json')
        self.assertEqual(resp.status_code, 405)
