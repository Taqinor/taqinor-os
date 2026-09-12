"""NTOBS14 — historique d'uptime affiché en frise chronologique 90 jours."""
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from ..models import ComponentStatus, UptimeDayBucket
from ..tasks import _accumuler_uptime_jour, rafraichir_composants


class AccumulerUptimeJourTest(TestCase):
    def test_first_tick_creates_bucket_at_100_percent(self):
        now = timezone.now()
        _accumuler_uptime_jour(
            'API', 'EU-West/Hetzner', ComponentStatus.Statut.OPERATIONAL, now)
        bucket = UptimeDayBucket.objects.get(composant='API', date=now.date())
        self.assertEqual(bucket.echantillons_total, 1)
        self.assertEqual(float(bucket.pct_disponible_jour), 100.0)

    def test_pct_reflects_mixed_ticks(self):
        now = timezone.now()
        _accumuler_uptime_jour(
            'API', 'EU-West/Hetzner', ComponentStatus.Statut.OPERATIONAL, now)
        _accumuler_uptime_jour(
            'API', 'EU-West/Hetzner', ComponentStatus.Statut.MAJOR_OUTAGE, now)
        _accumuler_uptime_jour(
            'API', 'EU-West/Hetzner', ComponentStatus.Statut.OPERATIONAL, now)
        bucket = UptimeDayBucket.objects.get(composant='API', date=now.date())
        self.assertEqual(bucket.echantillons_total, 3)
        self.assertEqual(bucket.echantillons_operationnels, 2)
        self.assertAlmostEqual(float(bucket.pct_disponible_jour), 66.67, places=1)

    def test_worst_of_day_is_kept_even_after_recovery(self):
        now = timezone.now()
        _accumuler_uptime_jour(
            'API', 'EU-West/Hetzner', ComponentStatus.Statut.MAJOR_OUTAGE, now)
        _accumuler_uptime_jour(
            'API', 'EU-West/Hetzner', ComponentStatus.Statut.OPERATIONAL, now)
        bucket = UptimeDayBucket.objects.get(composant='API', date=now.date())
        self.assertEqual(bucket.statut_pire_du_jour, ComponentStatus.Statut.MAJOR_OUTAGE)

    def test_never_raises_on_db_error(self):
        with mock.patch(
                'apps.statuspage.tasks.UptimeDayBucket.objects.get_or_create',
                side_effect=RuntimeError('boom')):
            _accumuler_uptime_jour(
                'API', 'EU-West/Hetzner', ComponentStatus.Statut.OPERATIONAL,
                timezone.now())  # ne doit rien lever


class RafraichirComposantsPopulatesBucketsTest(TestCase):
    def test_beat_task_populates_todays_buckets(self):
        fake_services = [
            {'name': 'database', 'status': 'ok', 'detail': ''},
            {'name': 'cache', 'status': 'ok', 'detail': ''},
            {'name': 'storage', 'status': 'ok', 'detail': ''},
            {'name': 'broker', 'status': 'ok', 'detail': ''},
            {'name': 'queue', 'status': 'ok', 'detail': ''},
        ]
        with mock.patch(
                'apps.statuspage.tasks.check_services',
                return_value=fake_services):
            rafraichir_composants()
        today = timezone.now().date()
        self.assertTrue(
            UptimeDayBucket.objects.filter(composant='API', date=today).exists())
        self.assertGreaterEqual(
            UptimeDayBucket.objects.filter(date=today).count(), 5)


class PublicUptime90jEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs14')

    def test_returns_grouped_data_for_system_components(self):
        today = timezone.now().date()
        UptimeDayBucket.objects.create(
            company=None, composant='API', date=today,
            statut_pire_du_jour=ComponentStatus.Statut.OPERATIONAL,
            echantillons_total=10, echantillons_operationnels=10,
            pct_disponible_jour=100)
        resp = APIClient().get('/api/django/statuspage/public/uptime-90j/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('API', resp.data)
        self.assertEqual(len(resp.data['API']), 1)

    def test_never_leaks_company_specific_bucket(self):
        today = timezone.now().date()
        UptimeDayBucket.objects.create(
            company=self.company, composant='Composant privé', date=today,
            statut_pire_du_jour=ComponentStatus.Statut.OPERATIONAL)
        resp = APIClient().get('/api/django/statuspage/public/uptime-90j/')
        self.assertNotIn('Composant privé', resp.data)

    def test_excludes_buckets_older_than_90_days(self):
        vieux = timezone.now().date() - timezone.timedelta(days=120)
        UptimeDayBucket.objects.create(
            company=None, composant='API', date=vieux,
            statut_pire_du_jour=ComponentStatus.Statut.OPERATIONAL)
        resp = APIClient().get('/api/django/statuspage/public/uptime-90j/')
        self.assertNotIn('API', resp.data)
