"""PUB70 — Veille concurrentielle (périmètre HONNÊTE, zéro scraping).

Prouve : le finding API (couverture commerciale = NON) ; le lien Ad Library WEB
profond ; la cadence par concurrent sur des saisies MANUELLES ; les observations
transformées en matière de brief. Aucun appel réseau — que de la saisie humaine.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import competitor_intel as ci
from apps.adsengine.models import CompetitorAdObservation, CompetitorPage

User = get_user_model()


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ApiCoverageFindingTests(TestCase):
    def test_api_does_not_cover_commercial(self):
        self.assertFalse(ci.ad_library_api_covers_commercial('MA'))
        self.assertFalse(ci.AD_LIBRARY_API_FINDING['covers_commercial'])
        self.assertEqual(
            ci.AD_LIBRARY_API_FINDING['automation_status'], 'GATED')


class DeepLinkTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Veille Co', slug='veille-co')

    def test_deep_link_with_page_id(self):
        page = CompetitorPage.objects.create(
            company=self.company, name='SolaireX', page_id='12345',
            country='MA')
        url = page.ad_library_url()
        self.assertIn('view_all_page_id=12345', url)
        self.assertIn('country=MA', url)
        self.assertIn('facebook.com/ads/library', url)

    def test_deep_link_falls_back_to_name_search(self):
        page = CompetitorPage.objects.create(
            company=self.company, name='Solaire Y', country='MA')
        url = page.ad_library_url()
        self.assertIn('q=Solaire%20Y', url)


class CadenceTimelineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cad Co', slug='cad-co')
        self.today = datetime.date(2026, 7, 19)
        self.page = CompetitorPage.objects.create(
            company=self.company, name='Concurrent A')

    def _obs(self, day, hook='hook'):
        return CompetitorAdObservation.objects.create(
            company=self.company, competitor_page=self.page,
            observed_at=day, hook_text=hook, angle='ROI')

    def test_cadence_counts_manual_entries_per_week(self):
        self._obs(datetime.date(2026, 7, 15))
        self._obs(datetime.date(2026, 7, 16))
        self._obs(datetime.date(2026, 7, 8))
        rows = ci.cadence_timeline(self.company, weeks=8, today=self.today)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['total'], 3)
        self.assertEqual(len(rows[0]['par_semaine']), 2)  # deux semaines ISO

    def test_brief_material_excludes_empty_observations(self):
        self._obs(datetime.date(2026, 7, 15), hook='Économisez dès le 1er mois')
        CompetitorAdObservation.objects.create(
            company=self.company, competitor_page=self.page,
            observed_at=self.today, hook_text='', angle='')  # vide → ignorée
        material = ci.observations_as_brief_material(self.company)
        self.assertEqual(len(material), 1)
        self.assertIn('Économisez', material[0]['hook_text'])


class VeilleApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Api Co', slug='api-co')
        self.user = make_user(
            self.company, 'veille_mgr',
            ['adsengine_view', 'adsengine_manage'])

    def test_veille_endpoint_returns_finding(self):
        CompetitorPage.objects.create(company=self.company, name='X')
        resp = auth(self.user).get('/api/django/adsengine/concurrents/veille/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['finding']['covers_commercial'])
        self.assertIn('cadence', resp.data)
        self.assertIn('brief_material', resp.data)

    def test_competitor_create_forces_company(self):
        other = Company.objects.create(nom='Other', slug='other-veille')
        resp = auth(self.user).post(
            '/api/django/adsengine/concurrents/',
            {'name': 'NouveauConcurrent', 'company': other.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        page = CompetitorPage.objects.get(id=resp.data['id'])
        self.assertEqual(page.company_id, self.company.id)
