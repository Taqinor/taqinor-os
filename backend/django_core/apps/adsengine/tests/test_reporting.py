"""ADSENG33 — Tests des drill-downs de reporting (fixtures multi-semaines).

Prouve : table par variante (dépense/conv/CPL/coût-signature + ids), entonnoir
par campagne (cumulatif NEW→SIGNED, COLD/perdu à côté), cohortes de signature
(leads/semaine → lag, cohortes incomplètes marquées), export CSV (variantes +
réconciliation), et le gating ``adsengine_view`` des endpoints.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Client, Lead
from apps.crm.stages import CONTACTED, COLD, NEW, QUOTE_SENT, SIGNED
from apps.ventes.models import Devis

from apps.adsengine import reporting
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, InsightSnapshot,
)

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


class VariantTableTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Var Co', slug='var-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_1', name='Solaire', status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_1', name='Toit', campaign=self.camp)
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad_100', name='Reel', adset=self.adset)
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def test_variant_table_has_cost_columns_and_lead_ids(self):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.ad.pk,
            date=datetime.date(2026, 7, 16), spend=Decimal('300.00'), results=1)
        for _ in range(2):
            Lead.objects.create(
                company=self.company, nom='P', stage=SIGNED,
                meta_ad_id='ad_100', canal=Lead.Canal.META_ADS)
        Lead.objects.create(
            company=self.company, nom='P', stage=CONTACTED,
            meta_ad_id='ad_100', canal=Lead.Canal.META_ADS)

        table = reporting.variant_table(self.company)
        v = table['variants'][0]
        self.assertEqual(v['meta_id'], 'ad_100')
        self.assertEqual(v['leads'], 3)
        self.assertEqual(v['signed'], 2)
        # coût-par-lead = 300 / 3 = 100 ; coût-par-signature = 300 / 2 = 150.
        self.assertEqual(v['cost_per_lead'], '100.00')
        self.assertEqual(v['cost_per_signature'], '150.00')
        self.assertEqual(len(v['lead_ids']), 3)

    def test_endpoint_gated(self):
        viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        nobody = make_user(self.company, 'nobody', [])
        url = '/api/django/adsengine/reporting/variantes/'
        self.assertEqual(auth(viewer).get(url).status_code, 200)
        self.assertEqual(auth(nobody).get(url).status_code, 403)


class CampaignFunnelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Fun Co', slug='fun-co')

    def _lead(self, stage, **kw):
        return Lead.objects.create(
            company=self.company, nom='P', stage=stage,
            meta_campaign_id='cmp1', canal=Lead.Canal.META_ADS, **kw)

    def test_cumulative_funnel_cold_and_perdu_aside(self):
        for _ in range(3):
            self._lead(NEW)
        for _ in range(2):
            self._lead(QUOTE_SENT)
        self._lead(SIGNED)
        self._lead(COLD)
        self._lead(CONTACTED, perdu=True)

        funnel = reporting.campaign_funnel(self.company)
        entry = [e for e in funnel if e['campaign_key'] == 'cmp1'][0]
        self.assertEqual(entry['total'], 8)
        self.assertEqual(entry['cold'], 1)
        self.assertEqual(entry['perdu'], 1)
        reached = {b['stage']: b['reached'] for b in entry['funnel']}
        self.assertEqual(reached[NEW], 6)
        self.assertEqual(reached[CONTACTED], 3)
        self.assertEqual(reached[QUOTE_SENT], 3)
        self.assertEqual(reached[SIGNED], 1)

    def test_endpoint_returns_funnel(self):
        viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self._lead(NEW)
        resp = auth(viewer).get('/api/django/adsengine/reporting/entonnoir/')
        self.assertEqual(resp.status_code, 200)


class CohortTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Coh Co', slug='coh-co')
        self.client_obj = Client.objects.create(company=self.company, nom='C')
        self._ref = 0

    def _lead(self, created, *, signed_on=None):
        lead = Lead.objects.create(
            company=self.company, nom='P', stage=(SIGNED if signed_on else NEW),
            canal=Lead.Canal.META_ADS)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.make_aware(
                datetime.datetime.combine(created, datetime.time(12, 0))))
        if signed_on is not None:
            self._ref += 1
            Devis.objects.create(
                company=self.company, reference=f'DEV-{self._ref:04d}',
                client=self.client_obj, lead=lead, statut='accepte',
                date_acceptation=signed_on)
        return lead

    def test_cohorts_group_by_week_with_lag_and_incompleteness(self):
        old = datetime.date(2026, 6, 1)
        recent = datetime.date(2026, 7, 13)
        today = datetime.date(2026, 7, 16)
        # cohorte ancienne : 2 leads, 1 signe à J+4 jours (bucket 1 semaine).
        self._lead(old, signed_on=old + datetime.timedelta(days=4))
        self._lead(old)
        # cohorte récente : 1 lead non encore signé (buckets longs incomplets).
        self._lead(recent)

        cohorts = reporting.signature_cohorts(self.company, today=today)
        by_week = {c['cohort_week']: c for c in cohorts}

        old_ws = old - datetime.timedelta(days=old.weekday())
        recent_ws = recent - datetime.timedelta(days=recent.weekday())
        old_c = by_week[old_ws.isoformat()]
        self.assertEqual(old_c['total_leads'], 2)
        self.assertEqual(old_c['signed_total'], 1)
        b1 = [b for b in old_c['lag_buckets'] if b['lag_weeks'] == 1][0]
        self.assertEqual(b1['signed'], 1)
        self.assertTrue(b1['complete'])  # >6 semaines écoulées → complet.

        recent_c = by_week[recent_ws.isoformat()]
        b12 = [b for b in recent_c['lag_buckets'] if b['lag_weeks'] == 12][0]
        # fenêtre 12 sem. non écoulée (créée il y a ~3 j) → marquée incomplète.
        self.assertFalse(b12['complete'])

    def test_endpoint_returns_cohorts(self):
        viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self._lead(datetime.date(2026, 7, 1))
        resp = auth(viewer).get('/api/django/adsengine/reporting/cohortes/')
        self.assertEqual(resp.status_code, 200)


class CsvExportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Csv Co', slug='csv-co')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_1', name='Solaire', status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_1', name='Toit', campaign=self.camp)
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad_100', name='Reel', adset=self.adset)
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def test_variant_csv_has_header_and_row(self):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.ad.pk,
            date=datetime.date(2026, 7, 16), spend=Decimal('100.00'), results=1)
        Lead.objects.create(
            company=self.company, nom='P', stage=SIGNED, meta_ad_id='ad_100',
            canal=Lead.Canal.META_ADS)
        csv_text = reporting.variant_table_csv(self.company)
        self.assertIn('meta_id,name,spend', csv_text)
        self.assertIn('ad_100', csv_text)

    def test_reconciliation_csv_builds(self):
        csv_text = reporting.reconciliation_csv(
            self.company, day=datetime.date(2026, 7, 16))
        self.assertIn('campaign_meta_id,campaign_name', csv_text)

    def test_export_endpoint_returns_csv(self):
        resp = auth(self.viewer).get(
            '/api/django/adsengine/reporting/export/?table=variantes')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])

    def test_export_reconciliation_variant(self):
        resp = auth(self.viewer).get(
            '/api/django/adsengine/reporting/export/?table=reconciliation')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('reconciliation.csv', resp['Content-Disposition'])
