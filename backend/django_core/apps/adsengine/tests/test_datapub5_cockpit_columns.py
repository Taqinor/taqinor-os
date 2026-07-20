"""DATAPUB5 — Parité colonnes Ads Manager au cockpit.

``metrics.ads_cockpit_rows`` porte désormais les champs BRUTS (impressions,
couverture, clics, clics sur lien, résultats) et les métriques DÉRIVÉES
(CTR/CPC/CPM, hook/hold) — None honnête quand un dénominateur manque (jamais un
ratio fabriqué).
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.metrics import ads_cockpit_rows


class CockpitColumnParityTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cp Co', slug='cp')

    def test_raw_and_derived_columns_present(self):
        ad = sync.sync_ads(self.company, [{'id': 'ad1', 'name': 'AD1'}])[0]
        sync.upsert_insight(
            self.company, ad, date=datetime.date(2026, 7, 16),
            spend='300.00', impressions=10000, clicks=200, reach=8000,
            link_clicks=150, results=5,
            video_metrics={'s6': 3000, 'plays': 5000, 'thruplay': 2000})
        row = next(r for r in ads_cockpit_rows(self.company)
                   if r['meta_id'] == 'ad1')
        self.assertEqual(row['impressions'], 10000)
        self.assertEqual(row['reach'], 8000)
        self.assertEqual(row['clics'], 200)
        self.assertEqual(row['clics_lien'], 150)
        self.assertEqual(row['resultats'], 5)
        # Dérivées : CTR = 200/10000 ; CPC = 300/200 ; CPM = 300*1000/10000.
        self.assertAlmostEqual(row['ctr'], 0.02)
        self.assertEqual(row['cpc_mad'], '1.50')
        self.assertEqual(row['cpm_mad'], '30.00')
        # Vidéo : hook = 3000/10000 ; hold = 2000/5000.
        self.assertAlmostEqual(row['hook_rate'], 0.30)
        self.assertAlmostEqual(row['hold_rate'], 0.40)

    def test_derived_metrics_are_none_when_inputs_missing(self):
        ad = sync.sync_ads(self.company, [{'id': 'ad2', 'name': 'AD2'}])[0]
        # Dépense seule : ni impressions ni clics → pas de CTR/CPC/CPM fabriqués.
        sync.upsert_insight(
            self.company, ad, date=datetime.date(2026, 7, 16), spend='50.00')
        row = next(r for r in ads_cockpit_rows(self.company)
                   if r['meta_id'] == 'ad2')
        self.assertIsNone(row['ctr'])
        self.assertIsNone(row['cpc_mad'])
        self.assertIsNone(row['cpm_mad'])
        self.assertIsNone(row['hook_rate'])
        self.assertIsNone(row['hold_rate'])
