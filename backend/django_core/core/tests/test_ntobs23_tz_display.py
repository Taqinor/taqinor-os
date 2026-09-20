"""NTOBS23 — fuseau horaire d'affichage par tenant (IncidentPublic/
SlaSnapshot/MaintenanceWindow, NTOBS1/3/9)."""
import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone as dj_timezone
from rest_framework.test import APIClient

from apps.parametres.models_company import CompanyProfile
from django.apps import apps as django_apps
from authentication.models import Company
from core.maintenance_windows import MaintenanceWindow
from core.sla import generer_snapshot_societe
from core.tz_display import DEFAULT_TIMEZONE, to_company_tz

# Pas d'import statique d'une app domaine sous core (contrat import-linter M3)
IncidentPublic = django_apps.get_model('statuspage', 'IncidentPublic')

User = get_user_model()


class ToCompanyTzUnitTest(SimpleTestCase):
    def test_none_datetime_returns_none(self):
        self.assertIsNone(to_company_tz(None, None))

    def test_no_company_falls_back_to_default(self):
        dt = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo('UTC'))
        result = to_company_tz(dt, None)
        self.assertEqual(str(result.tzinfo), DEFAULT_TIMEZONE)

    def test_naive_datetime_is_treated_as_utc(self):
        naive = datetime.datetime(2026, 6, 1, 12, 0)
        result = to_company_tz(naive, None)
        self.assertIsNotNone(result.tzinfo)


class ToCompanyTzWithProfileTest(TestCase):
    def test_uses_company_profile_timezone(self):
        company = Company.objects.create(nom='Acme', slug='ntobs23-acme')
        profile = CompanyProfile.get(company)
        profile.timezone_affichage = 'America/New_York'
        profile.save(update_fields=['timezone_affichage'])

        dt = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo('UTC'))
        result = to_company_tz(dt, company)
        self.assertEqual(str(result.tzinfo), 'America/New_York')
        # 12:00 UTC en juin (EDT, UTC-4) -> 08:00 locale.
        self.assertEqual(result.hour, 8)

    def test_invalid_timezone_name_falls_back_to_default(self):
        company = Company.objects.create(nom='Acme', slug='ntobs23-bad-tz')
        profile = CompanyProfile.get(company)
        profile.timezone_affichage = 'Pas/UnFuseau'
        profile.save(update_fields=['timezone_affichage'])

        dt = datetime.datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo('UTC'))
        result = to_company_tz(dt, company)
        self.assertEqual(str(result.tzinfo), DEFAULT_TIMEZONE)


class MaintenanceWindowLocalTimestampsTest(TestCase):
    """Une fenêtre SYSTÈME-WIDE (company=None) doit s'afficher à des heures
    locales DIFFÉRENTES pour deux sociétés de fuseaux différents — la
    conversion se fait sur le fuseau du VIEWER, pas de la fenêtre."""

    def setUp(self):
        self.casa = Company.objects.create(nom='Casa', slug='ntobs23-casa')
        self.tokyo = Company.objects.create(nom='Tokyo', slug='ntobs23-tokyo')
        profile = CompanyProfile.get(self.tokyo)
        profile.timezone_affichage = 'Asia/Tokyo'
        profile.save(update_fields=['timezone_affichage'])

        self.user_casa = User.objects.create_user(
            'u_casa', password='x', company=self.casa)
        self.user_tokyo = User.objects.create_user(
            'u_tokyo', password='x', company=self.tokyo)

        now = dj_timezone.now()
        self.fenetre = MaintenanceWindow.objects.create(
            company=None, debute_le=now + datetime.timedelta(hours=1),
            termine_le=now + datetime.timedelta(hours=2),
            description='Maintenance système large.')

    def _get_local_debute(self, user):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/django/core/maintenance-windows/actives/')
        self.assertEqual(resp.status_code, 200)
        return resp.data[0]['debute_le_local']

    def test_two_companies_see_different_local_hours(self):
        casa_local = self._get_local_debute(self.user_casa)
        tokyo_local = self._get_local_debute(self.user_tokyo)
        self.assertNotEqual(casa_local, tokyo_local)


class SlaSnapshotLocalTimestampTest(TestCase):
    def test_genere_le_local_present_and_scoped_to_snapshot_company(self):
        company = Company.objects.create(nom='Acme', slug='ntobs23-sla')
        profile = CompanyProfile.get(company)
        profile.timezone_affichage = 'Asia/Tokyo'
        profile.save(update_fields=['timezone_affichage'])
        generer_snapshot_societe(company, datetime.date(2026, 6, 1))

        user = User.objects.create_user('u1', password='x', company=company)
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/django/core/sla/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('genere_le_local', resp.data[0])
        self.assertIn('+09:00', resp.data[0]['genere_le_local'])


class IncidentPublicLocalTimestampTest(TestCase):
    def test_public_incident_exposes_local_fields(self):
        IncidentPublic.objects.create(
            titre='Panne API', company=None, debute_le=dj_timezone.now())
        resp = APIClient().get('/api/django/statuspage/public/incidents/')
        self.assertEqual(resp.status_code, 200)
        first = resp.data['results'][0] if isinstance(resp.data, dict) else resp.data[0]
        self.assertIn('debute_le_local', first)
