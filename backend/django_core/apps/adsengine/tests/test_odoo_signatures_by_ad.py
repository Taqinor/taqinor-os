"""ADSDEEP20 — Tests des signatures Odoo par AD : match téléphone (deal →
phone_key → MetaLeadMirror → ad_id), coût/signature par ad sur la dépense ad
réelle, deals traçables ; enrichissement de variant_attribution.
"""
import datetime
from unittest.mock import patch

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.attribution import variant_attribution
from apps.adsengine.models import MetaLeadMirror
from apps.adsengine.odoo_metrics import odoo_signatures_by_ad


def _seed_phone_key(company, telephone):
    from apps.crm.selectors import normalize_phone_key
    return normalize_phone_key(telephone)


class OdooSignaturesByAdTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='OS Co', slug='os')
        # ad1 avec dépense réelle (snapshot ADSDEEP2) + un lead miroité.
        self.ad = sync.sync_ads(self.company, [{'id': 'ad1', 'name': 'AD1'}])[0]
        sync.upsert_insight(
            self.company, self.ad, date=datetime.date(2026, 7, 16),
            spend='300.00')
        self.phone_key = _seed_phone_key(self.company, '+212612345678')
        MetaLeadMirror.objects.create(
            company=self.company, leadgen_id='lg1', ad_id='ad1',
            phone_key=self.phone_key, crm_lead_id=1)

    def _deals(self):
        return [
            {'phone_norm': self.phone_key, 'amount_mad': 1000, 'date': '2026-07-16',
             'source_name': 'x', 'origin': 'o', 'lead_id': 55},
            {'phone_norm': self.phone_key, 'amount_mad': 2000, 'date': '2026-07-17',
             'source_name': 'y', 'origin': 'o', 'lead_id': 56},
            {'phone_norm': 'unknownkey', 'amount_mad': 500, 'date': '2026-07-18',
             'source_name': 'z', 'origin': 'o', 'lead_id': 57},
        ]

    @patch('apps.adsengine.odoo_metrics.odoo_signed_deals')
    def test_signatures_and_cost_per_ad(self, mock_deals):
        mock_deals.return_value = self._deals()
        res = odoo_signatures_by_ad(self.company)
        self.assertEqual(res['attributed'], 2)
        self.assertEqual(res['unattributed'], 1)
        ad_row = next(a for a in res['ads'] if a['ad_id'] == 'ad1')
        self.assertEqual(ad_row['signatures'], 2)
        # coût/signature = dépense ad (300) / 2 = 150.
        self.assertEqual(ad_row['cost_per_signature'], '150.00')
        # deals traçables.
        self.assertEqual(sorted(ad_row['deal_ids']), [55, 56])

    @patch('apps.adsengine.odoo_metrics.odoo_signed_deals')
    def test_variant_attribution_enriched_with_odoo(self, mock_deals):
        mock_deals.return_value = self._deals()
        with patch('apps.adsengine.odoo_client.is_configured',
                   return_value=True):
            res = variant_attribution(self.company)
        row = next(v for v in res['variants'] if v['meta_id'] == 'ad1')
        self.assertEqual(row['odoo_signed'], 2)
        self.assertEqual(row['odoo_cost_per_signature'], '150.00')
        self.assertEqual(sorted(row['odoo_signed_deal_ids']), [55, 56])

    def test_variant_attribution_zero_odoo_without_config(self):
        # Sans connecteur Odoo configuré : odoo_signed = 0, aucun appel réseau.
        res = variant_attribution(self.company)
        row = next(v for v in res['variants'] if v['meta_id'] == 'ad1')
        self.assertEqual(row['odoo_signed'], 0)
        self.assertIsNone(row['odoo_cost_per_signature'])
