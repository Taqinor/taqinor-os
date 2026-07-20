"""DATAPUB2 — Bilan d'attribution des leads Odoo.

``reporting.attribution_bilan`` met en forme l'attribution
(``odoo_leads.odoo_leads_by_ad``) : total lu, répartition par palier FR, et
NON-attribués listés par nom de source. L'endpoint
``/reporting/attribution-bilan/`` l'expose, company-scopé, gaté ``adsengine_view``.
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
from apps.adsengine.reporting import attribution_bilan

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


class AttributionBilanFunctionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bil Co', slug='bil')
        ad = sync.sync_ads(self.company, [{'id': 'ad1', 'name': 'AD1'}])[0]
        sync.upsert_insight(
            self.company, ad, date=datetime.date(2026, 7, 16), spend='100.00')
        self.key = _phone_key('+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', ad_id='ad1',
            phone_key=self.key, crm_lead_id=1)

    def test_bilan_counts_all_leads_by_tier_and_source(self):
        leads = [
            {'phone_norm': self.key, 'date': None, 'source_name': 'x',
             'lead_id': 1, 'won': False},
            {'phone_norm': 'no1', 'date': None,
             'source_name': 'INCONNU FORM-9', 'lead_id': 2, 'won': False},
            {'phone_norm': 'no2', 'date': None,
             'source_name': 'INCONNU FORM-9', 'lead_id': 3, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            bilan = attribution_bilan(self.company)
        self.assertEqual(bilan['total'], 3)
        self.assertEqual(bilan['attributed'], 1)
        self.assertEqual(bilan['unattributed'], 2)
        tiers = {t['key']: t for t in bilan['tiers']}
        # ordre + libellés FR stables, tous les paliers présents.
        self.assertEqual([t['key'] for t in bilan['tiers']],
                         ['telephone', 'formulaire', 'formulaire_campagne',
                          'nom', 'date'])
        self.assertEqual(tiers['telephone']['count'], 1)
        self.assertEqual(tiers['telephone']['label'], 'Téléphone (exact)')
        self.assertEqual(tiers['nom']['count'], 0)
        by_source = {r['source_name']: r['count']
                     for r in bilan['unattributed_by_source']}
        self.assertEqual(by_source['INCONNU FORM-9'], 2)

    def test_bilan_noop_without_odoo(self):
        bilan = attribution_bilan(self.company)
        self.assertFalse(bilan['configured'])
        self.assertEqual(bilan['total'], 0)
        self.assertEqual([t['key'] for t in bilan['tiers']],
                         ['telephone', 'formulaire', 'formulaire_campagne',
                          'nom', 'date'])


class AttributionBilanEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Be Co', slug='be')
        self.viewer = _make_user(self.company, 'be-viewer', ['adsengine_view'])
        self.nobody = _make_user(self.company, 'be-nobody', [])

    def test_endpoint_gated_and_shaped(self):
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=[]):
            resp = _auth(self.viewer).get(
                f'{BASE}/reporting/attribution-bilan/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('tiers', resp.data)
        self.assertIn('unattributed_by_source', resp.data)
        self.assertEqual(resp.data['total'], 0)

    def test_endpoint_requires_permission(self):
        resp = _auth(self.nobody).get(f'{BASE}/reporting/attribution-bilan/')
        self.assertEqual(resp.status_code, 403)
