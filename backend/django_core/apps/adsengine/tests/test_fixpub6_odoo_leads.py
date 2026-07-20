"""FIXPUB6 — Leads Odoo attribués PAR ANNONCE (coût-par-lead).

``odoo_selectors.all_leads`` normalise TOUS les leads Odoo (no-op sans config) ;
``odoo_leads.odoo_leads_by_ad`` les attribue à une annonce en 3 paliers (exact
téléphone → estimation nom → estimation fenêtre date) et calcule ``cpl_odoo`` ;
``metrics.ads_cockpit_rows`` porte ``leads_odoo`` + ``cpl_odoo`` par ligne.
"""
import datetime
from unittest.mock import patch

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.metrics import ads_cockpit_rows
from apps.adsengine.models import MetaLeadMirror
from apps.adsengine.odoo_leads import odoo_leads_by_ad
from apps.adsengine.odoo_selectors import all_leads


def _phone_key(telephone):
    from apps.crm.selectors import normalize_phone_key
    return normalize_phone_key(telephone)


class FakeOdooClient:
    """Client Odoo mocké : ``read_leads`` renvoie des dicts bruts crm.lead."""

    def __init__(self, rows):
        self._rows = rows

    def read_leads(self, since=None):
        return list(self._rows)


class AllLeadsSelectorTests(TestCase):
    def test_normalizes_and_flags_won(self):
        client = FakeOdooClient([
            {'id': 1, 'name': 'Sara', 'phone': '+212612345678',
             'probability': 100, 'create_date': '2026-07-16 09:00:00'},
            {'id': 2, 'name': 'Karim', 'mobile': '+212698765432',
             'probability': 20, 'create_date': '2026-07-17 09:00:00'},
        ])
        rows = all_leads(client=client)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['phone_norm'], _phone_key('+212612345678'))
        self.assertTrue(rows[0]['won'])
        self.assertEqual(rows[1]['phone_norm'], _phone_key('+212698765432'))
        self.assertFalse(rows[1]['won'])

    def test_noop_without_config(self):
        # Aucune variable ODOO_* → OdooClient.from_env() None → [].
        self.assertEqual(all_leads(), [])


class OdooLeadsByAdTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='OL Co', slug='ol')

    def _seed_ad(self, meta_id, name, spend, day):
        ad = sync.sync_ads(self.company, [{'id': meta_id, 'name': name}])[0]
        sync.upsert_insight(self.company, ad, date=day, spend=spend)
        return ad

    def test_exact_phone_attribution_and_cpl(self):
        self._seed_ad('ad1', 'AD1', '300.00', datetime.date(2026, 7, 16))
        key = _phone_key('+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', ad_id='ad1',
            phone_key=key, crm_lead_id=1)
        leads = [
            {'phone_norm': key, 'date': None, 'source_name': 'x',
             'lead_id': 10, 'won': True},
            {'phone_norm': key, 'date': None, 'source_name': 'y',
             'lead_id': 11, 'won': False},
            {'phone_norm': 'unknownkey', 'date': None, 'source_name': '',
             'lead_id': 12, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 2)
        self.assertEqual(res['unattributed'], 1)
        row = next(a for a in res['ads'] if a['ad_id'] == 'ad1')
        self.assertEqual(row['leads_odoo'], 2)
        self.assertEqual(row['leads_exact'], 2)
        self.assertEqual(row['leads_estimes'], 0)
        self.assertEqual(row['attribution_type'], 'exact')
        # coût-par-lead = dépense ad (300) / 2 = 150.
        self.assertEqual(row['cpl_odoo'], '150.00')
        self.assertEqual(sorted(row['lead_ids']), [10, 11])

    def test_name_estimation_tier(self):
        self._seed_ad('ad2', 'TAQINOR FORM', '200.00',
                      datetime.date(2026, 7, 16))
        leads = [
            {'phone_norm': '', 'date': '2026-03-26 09:00:00',
             'source_name': 'DAZZLEMEDAI-TAQINOR FORM-26/03/2026',
             'lead_id': 20, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 1)
        row = next(a for a in res['ads'] if a['ad_id'] == 'ad2')
        self.assertEqual(row['leads_odoo'], 1)
        self.assertEqual(row['leads_estimes'], 1)
        self.assertEqual(row['attribution_type'], 'estimation')
        self.assertEqual(row['cpl_odoo'], '200.00')

    def test_date_window_estimation_tier(self):
        # Nom non exploitable + une SEULE annonce active le jour du lead.
        self._seed_ad('ad3', 'Pompage', '100.00', datetime.date(2026, 7, 20))
        leads = [
            {'phone_norm': '', 'date': '2026-07-20 11:00:00',
             'source_name': '', 'lead_id': 30, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 1)
        row = next(a for a in res['ads'] if a['ad_id'] == 'ad3')
        self.assertEqual(row['leads_odoo'], 1)
        self.assertEqual(row['attribution_type'], 'estimation')

    def test_unattributed_when_ambiguous_date(self):
        # Deux annonces actives le même jour → fenêtre date ambiguë → non attribué.
        self._seed_ad('ad4', 'A4', '100.00', datetime.date(2026, 7, 21))
        self._seed_ad('ad5', 'A5', '100.00', datetime.date(2026, 7, 21))
        leads = [
            {'phone_norm': '', 'date': '2026-07-21 08:00:00',
             'source_name': '', 'lead_id': 40, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            res = odoo_leads_by_ad(self.company)
        self.assertEqual(res['attributed'], 0)
        self.assertEqual(res['unattributed'], 1)

    def test_noop_without_odoo_config(self):
        self._seed_ad('ad1', 'AD1', '300.00', datetime.date(2026, 7, 16))
        res = odoo_leads_by_ad(self.company)
        self.assertFalse(res['configured'])
        self.assertEqual(res['ads'], [])


class CockpitLeadsOdooTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CK Co', slug='ck')
        self.ad = sync.sync_ads(
            self.company, [{'id': 'ad1', 'name': 'AD1'}])[0]
        sync.upsert_insight(
            self.company, self.ad, date=datetime.date(2026, 7, 16),
            spend='300.00')
        self.key = _phone_key('+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', ad_id='ad1',
            phone_key=self.key, crm_lead_id=1)

    def test_cockpit_row_carries_leads_odoo_and_cpl(self):
        leads = [
            {'phone_norm': self.key, 'date': None, 'source_name': 'x',
             'lead_id': 10, 'won': True},
            {'phone_norm': self.key, 'date': None, 'source_name': 'y',
             'lead_id': 11, 'won': False},
        ]
        with patch('apps.adsengine.odoo_leads.odoo_all_leads',
                   return_value=leads):
            rows = ads_cockpit_rows(self.company)
        row = next(r for r in rows if r['meta_id'] == 'ad1')
        self.assertEqual(row['leads_odoo'], 2)
        self.assertEqual(row['cpl_odoo'], '150.00')

    def test_cockpit_row_zero_without_odoo(self):
        rows = ads_cockpit_rows(self.company)
        row = next(r for r in rows if r['meta_id'] == 'ad1')
        self.assertEqual(row['leads_odoo'], 0)
        self.assertIsNone(row['cpl_odoo'])
