"""DATAPUB3 — Leads Odoo dans le temps.

``reporting.leads_timeseries`` agrège TOUS les leads Odoo par jour/semaine (par
leur date Odoo) avec le sous-total ATTRIBUÉ et la DÉPENSE en overlay ; drill par
annonce. L'endpoint ``/reporting/leads-timeseries/`` l'expose, gaté.
"""
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import sync
from apps.adsengine.models import MetaLeadMirror
from apps.adsengine.reporting import leads_timeseries

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


def _phone_key(telephone):
    from apps.crm.selectors import normalize_phone_key
    return normalize_phone_key(telephone)


class LeadsTimeseriesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ts Co', slug='ts')
        camp = sync.sync_campaigns(
            self.company, [{'id': 'camp1', 'name': 'Camp1'}])[0]
        # Dépense société = niveau campagne (overlay).
        sync.upsert_insight(
            self.company, camp, date=datetime.date(2026, 7, 16), spend='500.00')
        self.ad = sync.sync_ads(
            self.company, [{'id': 'ad1', 'name': 'AD1'}])[0]
        sync.upsert_insight(
            self.company, self.ad, date=datetime.date(2026, 7, 16),
            spend='300.00')
        self.key = _phone_key('+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', ad_id='ad1',
            phone_key=self.key, crm_lead_id=1)
        self.leads = [
            {'phone_norm': self.key, 'date': '2026-07-16 09:00:00',
             'source_name': 'x', 'lead_id': 1, 'won': False},
            {'phone_norm': 'nope', 'date': '2026-07-16 10:00:00',
             'source_name': 'AUTRE', 'lead_id': 2, 'won': False},
            {'phone_norm': 'nope2', 'date': '2026-07-17 11:00:00',
             'source_name': 'AUTRE', 'lead_id': 3, 'won': False},
        ]

    def test_daily_series_with_attributed_and_spend_overlay(self):
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=self.leads):
            res = leads_timeseries(self.company, granularity='day')
        self.assertEqual(res['granularity'], 'day')
        pts = {p['period']: p for p in res['points']}
        self.assertEqual(pts['2026-07-16']['leads_total'], 2)
        self.assertEqual(pts['2026-07-16']['leads_attributed'], 1)
        self.assertEqual(pts['2026-07-16']['spend'], '500.00')
        self.assertEqual(pts['2026-07-17']['leads_total'], 1)
        self.assertEqual(pts['2026-07-17']['leads_attributed'], 0)
        # pas de dépense campagne le 17 → 0.00 (jamais masqué).
        self.assertEqual(pts['2026-07-17']['spend'], '0.00')

    def test_weekly_rollup(self):
        # 2026-07-16 et 2026-07-17 tombent dans la même semaine ISO.
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=self.leads):
            res = leads_timeseries(self.company, granularity='week')
        self.assertEqual(res['granularity'], 'week')
        self.assertEqual(len(res['points']), 1)
        self.assertEqual(res['points'][0]['leads_total'], 3)
        self.assertEqual(res['points'][0]['leads_attributed'], 1)
        self.assertEqual(res['points'][0]['spend'], '500.00')

    def test_per_ad_drill_uses_ad_spend_and_direct_leads(self):
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=self.leads):
            res = leads_timeseries(self.company, ad_meta_id='ad1')
        pts = {p['period']: p for p in res['points']}
        # seul le lead attribué directement à ad1 (le 16) est compté.
        self.assertEqual(pts['2026-07-16']['leads_total'], 1)
        self.assertEqual(pts['2026-07-16']['leads_attributed'], 1)
        # dépense = niveau AD (300), pas la dépense société (500).
        self.assertEqual(pts['2026-07-16']['spend'], '300.00')
        self.assertNotIn('2026-07-17', pts)


class LeadsTimeseriesEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Te Co', slug='te')
        self.viewer = _make_user(self.company, 'te-viewer', ['adsengine_view'])
        self.nobody = _make_user(self.company, 'te-nobody', [])

    def test_endpoint_gated_and_shaped(self):
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=[]):
            resp = _auth(self.viewer).get(
                f'{BASE}/reporting/leads-timeseries/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('points', resp.data)
        self.assertEqual(resp.data['granularity'], 'day')

    def test_endpoint_requires_permission(self):
        resp = _auth(self.nobody).get(f'{BASE}/reporting/leads-timeseries/')
        self.assertEqual(resp.status_code, 403)
