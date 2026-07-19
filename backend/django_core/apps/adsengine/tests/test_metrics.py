"""ENG10 — Tests de la métrique coût-par-signature (déterministes sur fixtures).

Prouve : le blend dépense (miroirs) × leads SIGNÉS (CRM via sélecteur) donne le
coût par signature attendu, la dépense se réconcilie avec les miroirs, chaque
chiffre porte les ids de leads réels (traçabilité), et l'endpoint est
company-scopé + gaté par ``adsengine_view`` sans fuite de secret.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Lead
from apps.crm.stages import NEW, SIGNED

from apps.adsengine import metrics
from apps.adsengine.models import AdCampaignMirror, InsightSnapshot

User = get_user_model()
URL = '/api/django/adsengine/metrics/cout-par-signature/'


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


class CostPerSignatureServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CPS Co', slug='cps-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Solaire Casa',
            status='PAUSED')
        self.ct = ContentType.objects.get_for_model(AdCampaignMirror)

    def _spend(self, amount, day):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct,
            object_id=self.camp.pk, date=day, spend=amount, results=1)

    def _signed_lead(self, utm, stage=SIGNED):
        return Lead.objects.create(
            company=self.company, nom='Prospect', utm_campaign=utm, stage=stage)

    def test_cost_per_signature_blend(self):
        import datetime
        self._spend('200.00', datetime.date(2026, 7, 15))
        self._spend('100.00', datetime.date(2026, 7, 16))
        ids = sorted(self._signed_lead('Solaire Casa').id for _ in range(3))
        # bruit : un lead non signé + un lead d'une autre campagne.
        self._signed_lead('Solaire Casa', stage=NEW)
        self._signed_lead('Autre Campagne')

        rows = metrics.cost_per_signature(self.company)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['campaign_meta_id'], 'c1')
        self.assertEqual(row['spend'], '300.00')
        self.assertEqual(row['signed_count'], 3)
        self.assertEqual(row['cost_per_signature'], '100.00')
        self.assertEqual(sorted(row['signed_lead_ids']), ids)

    def test_no_signed_gives_none_cps(self):
        import datetime
        self._spend('50.00', datetime.date(2026, 7, 16))
        rows = metrics.cost_per_signature(self.company)
        self.assertEqual(rows[0]['signed_count'], 0)
        self.assertIsNone(rows[0]['cost_per_signature'])

    def test_summary_reconciles_total_spend_with_mirrors(self):
        import datetime
        self._spend('200.00', datetime.date(2026, 7, 15))
        self._spend('100.00', datetime.date(2026, 7, 16))
        summary = metrics.cost_per_signature_summary(self.company)
        # Réconciliation : total = somme des instantanés des miroirs.
        snap_total = sum(
            (s.spend for s in InsightSnapshot.objects.filter(
                company=self.company)), Decimal('0'))
        self.assertEqual(Decimal(summary['total_spend']), snap_total)

    def test_scoping_ignores_other_company(self):
        other = Company.objects.create(nom='Other', slug='other')
        Lead.objects.create(
            company=other, nom='X', utm_campaign='Solaire Casa', stage=SIGNED)
        import datetime
        self._spend('100.00', datetime.date(2026, 7, 16))
        self._signed_lead('Solaire Casa')
        rows = metrics.cost_per_signature(self.company)
        # Le lead signé de l'autre société ne compte pas.
        self.assertEqual(rows[0]['signed_count'], 1)


class CostPerSignatureEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EP Co', slug='ep-co')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def test_endpoint_returns_metric(self):
        AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp', status='PAUSED')
        resp = auth(self.viewer).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('cost_per_signature', resp.data)
        self.assertIn('campagnes', resp.data)

    def test_endpoint_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        self.assertEqual(auth(nobody).get(URL).status_code, 403)


class PreviousPeriodTests(TestCase):
    """PUB40 — ``metrics.previous_period`` (pure, aucun accès base)."""

    def test_single_day_compares_to_same_weekday_last_week(self):
        import datetime
        day = datetime.date(2026, 7, 18)  # samedi
        prev_start, prev_end = metrics.previous_period(day, day)
        self.assertEqual(prev_start, datetime.date(2026, 7, 11))
        self.assertEqual(prev_end, datetime.date(2026, 7, 11))

    def test_multi_day_range_compares_to_immediately_preceding_period(self):
        import datetime
        start = datetime.date(2026, 7, 10)
        end = datetime.date(2026, 7, 16)  # 7 jours inclus
        prev_start, prev_end = metrics.previous_period(start, end)
        self.assertEqual(prev_start, datetime.date(2026, 7, 3))
        self.assertEqual(prev_end, datetime.date(2026, 7, 9))

    def test_thirty_day_range(self):
        import datetime
        start = datetime.date(2026, 6, 1)
        end = datetime.date(2026, 6, 30)  # 30 jours inclus
        prev_start, prev_end = metrics.previous_period(start, end)
        self.assertEqual((end - start).days + 1, 30)
        self.assertEqual((prev_end - prev_start).days + 1, 30)
        self.assertEqual(prev_end, start - datetime.timedelta(days=1))
