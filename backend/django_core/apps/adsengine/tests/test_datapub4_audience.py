"""DATAPUB4 — Audience (démographie) + diagnostics de synchro des breakdowns.

(a) ``tasks.sync_breakdowns_for_campaign_detailed`` remonte le DÉTAIL par
    dimension (rows + error) au lieu d'avaler les échecs en silence — c'est ce
    qui explique pourquoi seule ``age_gender`` se peuplait en prod.
(b) ``reporting.audience_breakdown`` agrège par genre/âge (FR, reach « — »
    honnête) ; l'endpoint ``/reporting/audience/`` l'expose, gaté.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import sync
from apps.adsengine.models import InsightBreakdown
from apps.adsengine.reporting import audience_breakdown
from apps.adsengine.tasks import (
    sync_breakdowns_for_campaign, sync_breakdowns_for_campaign_detailed,
)

User = get_user_model()
BASE = '/api/django/adsengine'


def _make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PartialBreakdownClient:
    """get_insights renvoie age_gender mais LÈVE pour les 3 autres dimensions
    (reproduit le rejet de combo observé en prod)."""

    def get_insights(self, meta_id, *, fields=None, params=None):
        bd = (params or {}).get('breakdowns', '')
        if 'age' in bd:
            return [{'age': '25-34', 'gender': 'female', 'spend': '10',
                     'impressions': '100', 'clicks': '5'}]
        raise RuntimeError('(#100) breakdown combo rejeté')


class BreakdownDiagnosticsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bd Co', slug='bdd')
        self.camp = sync.sync_campaigns(self.company, [{'id': 'c1'}])[0]

    def test_detailed_surfaces_per_dimension_error(self):
        detail = sync_breakdowns_for_campaign_detailed(
            self.company, PartialBreakdownClient(), self.camp)
        # age_gender a réussi (1 ligne, pas d'erreur)…
        self.assertEqual(detail['age_gender']['rows'], 1)
        self.assertIsNone(detail['age_gender']['error'])
        # …les 3 autres portent l'erreur au lieu d'un silence.
        for dim in ('platform', 'region', 'hourly'):
            self.assertEqual(detail[dim]['rows'], 0)
            self.assertIn('rejeté', detail[dim]['error'])
        # Seule age_gender est en base (comme en prod).
        dims = set(InsightBreakdown.objects.filter(company=self.company)
                   .values_list('dimension', flat=True))
        self.assertEqual(dims, {'age_gender'})

    def test_wrapper_keeps_int_total_contract(self):
        total = sync_breakdowns_for_campaign(
            self.company, PartialBreakdownClient(), self.camp)
        self.assertEqual(total, 1)


class AudienceBreakdownTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Au Co', slug='au')
        self.camp = sync.sync_campaigns(self.company, [{'id': 'c1'}])[0]
        day = datetime.date(2026, 7, 16)
        InsightBreakdown.upsert(
            self.company, self.camp, date=day, dimension='age_gender',
            key='25-34/f', spend=Decimal('10.00'), impressions=100, clicks=5,
            results=2, conversations=1)
        InsightBreakdown.upsert(
            self.company, self.camp, date=day, dimension='age_gender',
            key='25-34/m', spend=Decimal('8.00'), impressions=80, clicks=4,
            results=1)  # conversations non renseignées → None honnête
        InsightBreakdown.upsert(
            self.company, self.camp, date=day, dimension='age_gender',
            key='35-44/f', spend=Decimal('5.00'), impressions=50, clicks=2,
            results=0)

    def test_aggregates_by_gender_fr(self):
        res = audience_breakdown(self.company)
        self.assertTrue(res['configured'])
        by_g = {g['label']: g for g in res['by_gender']}
        # Femmes = 25-34/f + 35-44/f.
        self.assertEqual(by_g['Femmes']['impressions'], 150)
        self.assertEqual(by_g['Femmes']['results'], 2)
        self.assertEqual(by_g['Femmes']['spend'], '15.00')
        self.assertEqual(by_g['Femmes']['conversations'], 1)
        # reach jamais fabriqué (non stocké sous breakdown).
        self.assertIsNone(by_g['Femmes']['reach'])
        # Hommes : conversations JAMAIS renseignées → None (« — »), pas 0.
        self.assertEqual(by_g['Hommes']['impressions'], 80)
        self.assertIsNone(by_g['Hommes']['conversations'])
        # ordre FR : Femmes avant Hommes.
        self.assertEqual([g['label'] for g in res['by_gender']],
                         ['Femmes', 'Hommes'])

    def test_aggregates_by_age(self):
        res = audience_breakdown(self.company)
        by_a = {a['age']: a for a in res['by_age']}
        self.assertEqual(by_a['25-34']['impressions'], 180)
        self.assertEqual(by_a['25-34']['results'], 3)
        self.assertEqual(by_a['35-44']['impressions'], 50)

    def test_coverage_shows_only_age_gender_populated(self):
        res = audience_breakdown(self.company)
        cov = {c['dimension']: c for c in res['coverage']}
        self.assertEqual(cov['age_gender']['rows'], 3)
        self.assertEqual(cov['platform']['rows'], 0)
        self.assertEqual(cov['region']['rows'], 0)
        self.assertEqual(cov['hourly']['rows'], 0)

    def test_empty_when_no_breakdown(self):
        other = Company.objects.create(nom='Empty Co', slug='empty')
        res = audience_breakdown(other)
        self.assertFalse(res['configured'])
        self.assertEqual(res['by_gender'], [])
        self.assertEqual(res['by_age'], [])


class AudienceEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ae Co', slug='ae')
        self.viewer = _make_user(self.company, 'ae-viewer', ['adsengine_view'])
        self.nobody = _make_user(self.company, 'ae-nobody', [])

    def test_endpoint_gated_and_shaped(self):
        resp = _auth(self.viewer).get(f'{BASE}/reporting/audience/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('by_gender', resp.data)
        self.assertIn('by_age', resp.data)
        self.assertIn('coverage', resp.data)

    def test_endpoint_requires_permission(self):
        resp = _auth(self.nobody).get(f'{BASE}/reporting/audience/')
        self.assertEqual(resp.status_code, 403)
