"""VX61 — beacon Web Vitals RÉELS (POST company-scopé) + agrégat p75 +
politique de rétention (YOPSB10)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.reporting.models import WebVitalMetric
from apps.reporting.services import purge_web_vitals
from authentication.models import Company

User = get_user_model()

VITALS_URL = '/api/django/reporting/vitals/'
P75_URL = '/api/django/reporting/vitals/p75/'


def _auth(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VitalsCollectionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='vx61-co', defaults={'nom': 'VX61 Co'})[0]
        self.other_company = Company.objects.get_or_create(
            slug='vx61-other', defaults={'nom': 'VX61 Other'})[0]
        self.user = User.objects.create_user(
            username='vx61_u', password='x', company=self.company)
        self.api = _auth(self.user)

    def test_post_creates_row_scoped_to_company(self):
        resp = self.api.post(VITALS_URL, {
            'route': '/ventes/devis', 'metric': 'LCP', 'value': 2100.5,
            'rating': 'good', 'navigation_id': 'nav-1',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        row = WebVitalMetric.objects.get()
        self.assertEqual(row.company_id, self.company.id)
        self.assertEqual(row.utilisateur_id, self.user.id)
        self.assertEqual(row.metric, 'LCP')
        self.assertEqual(row.route, '/ventes/devis')

    def test_company_never_read_from_body(self):
        """company posée côté serveur : un corps qui tente de la forcer est
        ignoré — jamais lue de la requête (le serializer ne l'expose pas)."""
        resp = self.api.post(VITALS_URL, {
            'route': '/x', 'metric': 'CLS', 'value': 0.05,
            'company': self.other_company.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        row = WebVitalMetric.objects.get()
        self.assertEqual(row.company_id, self.company.id)

    def test_unknown_metric_rejected(self):
        resp = self.api.post(VITALS_URL, {
            'route': '/x', 'metric': 'BOGUS', 'value': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_rejected(self):
        resp = APIClient().post(VITALS_URL, {
            'route': '/x', 'metric': 'TTFB', 'value': 500,
        }, format='json')
        self.assertEqual(resp.status_code, 401)


class VitalsP75Tests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='vx61-p75-co', defaults={'nom': 'VX61 P75 Co'})[0]
        self.other_company = Company.objects.get_or_create(
            slug='vx61-p75-other', defaults={'nom': 'VX61 P75 Other'})[0]
        self.user = User.objects.create_user(
            username='vx61_p75_u', password='x', company=self.company)
        self.api = _auth(self.user)

    def _seed(self, company, route, metric, values):
        for v in values:
            WebVitalMetric.objects.create(
                company=company, route=route, metric=metric, value=v)

    def test_p75_computed_per_metric_and_scoped_to_company(self):
        # 100 valeurs 1..100 → p75 (tri simple, idx round(.75*99)=74) = 75.
        self._seed(self.company, '/dashboard', WebVitalMetric.Metric.LCP,
                   list(range(1, 101)))
        # Bruit sur une AUTRE société — ne doit jamais influencer l'agrégat.
        self._seed(self.other_company, '/dashboard', WebVitalMetric.Metric.LCP,
                   [9999] * 50)

        resp = self.api.get(P75_URL, {'route': '/dashboard'})
        self.assertEqual(resp.status_code, 200)
        lcp = resp.data['metrics']['LCP']
        self.assertEqual(lcp['count'], 100)
        self.assertEqual(lcp['p75'], 75)

    def test_no_data_returns_none_p75_zero_count(self):
        resp = self.api.get(P75_URL, {'route': '/rien'})
        self.assertEqual(resp.status_code, 200)
        for metric in WebVitalMetric.Metric.values:
            self.assertIsNone(resp.data['metrics'][metric]['p75'])
            self.assertEqual(resp.data['metrics'][metric]['count'], 0)


class VitalsRetentionTests(TestCase):
    """VX61 — la table grossit vite : purge programmée (registre YOPSB10)."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='vx61-retention-co', defaults={'nom': 'VX61 Retention Co'})[0]

    def test_purge_removes_only_rows_older_than_window(self):
        now = timezone.now()
        old = WebVitalMetric.objects.create(
            company=self.company, route='/x', metric='LCP', value=1000)
        WebVitalMetric.objects.filter(pk=old.pk).update(
            created_at=now - timezone.timedelta(days=45))
        recent = WebVitalMetric.objects.create(
            company=self.company, route='/x', metric='LCP', value=1000)

        with self.settings(WEB_VITALS_RETENTION_DAYS=30):
            # Dry-run : ne supprime rien, renvoie le compte qui SERAIT purgé.
            count_dry = purge_web_vitals(now, False)
            self.assertEqual(count_dry, 1)
            self.assertEqual(WebVitalMetric.objects.count(), 2)

            count_apply = purge_web_vitals(now, True)
            self.assertEqual(count_apply, 1)

        remaining = list(WebVitalMetric.objects.values_list('pk', flat=True))
        self.assertEqual(remaining, [recent.pk])

    def test_zero_or_negative_window_disables_purge(self):
        WebVitalMetric.objects.create(
            company=self.company, route='/x', metric='LCP', value=1000)
        with self.settings(WEB_VITALS_RETENTION_DAYS=0):
            count = purge_web_vitals(timezone.now(), True)
        self.assertEqual(count, 0)
        self.assertEqual(WebVitalMetric.objects.count(), 1)

    def test_policy_registered_in_shared_registry(self):
        from core.retention import list_retention_policies
        self.assertIn('reporting_web_vitals', list_retention_policies())
