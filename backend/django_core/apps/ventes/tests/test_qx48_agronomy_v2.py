"""QX48 — Moteur agronomique v2 (FAO-56 réel, série mensuelle) : test backend +
PARITÉ avec le miroir frontend agronomy.js.

Les valeurs canoniques ci-dessous sont IDENTIQUES à celles asserties dans
frontend/src/features/ventes/agronomy.v2.test.jsx — tout écart révèle un miroir
front/back désaligné.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx48_agronomy_v2 -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole import agronomy as a


class TestMonthlySeries(SimpleTestCase):
    def test_twelve_month_series(self):
        r = a.monthly_water_demand(
            crop='agrumes', region='souss-massa', surface_ha=2, method='goutte')
        self.assertEqual(len(r['kc']), 12)
        self.assertEqual(len(r['etc_mm_day']), 12)
        self.assertEqual(len(r['gross_m3_farm_day']), 12)
        # pic d'été > creux d'hiver
        self.assertGreater(r['gross_m3_farm_day'][6], r['gross_m3_farm_day'][0])

    def test_unknown_crop_flat_kc(self):
        # jamais d'exception ; culture inconnue → Kc plat 0.85
        r = a.monthly_water_demand(crop='zzz', region='mars', surface_ha=1)
        self.assertEqual(len(r['kc']), 12)
        self.assertEqual(a.crop_kc_monthly('zzz')[:3], [0.85, 0.85, 0.85])

    def test_irrigation_method_changes_gross(self):
        base = dict(crop='agrumes', region='souss-massa', surface_ha=2)
        goutte = a.monthly_water_demand(method='goutte', **base)
        grav = a.monthly_water_demand(method='gravitaire', **base)
        self.assertGreater(grav['annual_gross_m3_ha'], goutte['annual_gross_m3_ha'])


class TestCitedValues(SimpleTestCase):
    """3 valeurs Maroc CITÉES (recherche 2026-07-16) — calage du moteur."""

    def test_avocatier_gharb_in_cited_band(self):
        r = a.monthly_water_demand(
            crop='avocatier', region='gharb-loukkos', surface_ha=1, method='goutte')
        self.assertEqual(r['annual_gross_m3_ha'], 10084)  # parité JS
        lo, hi = a.CROP_CITED['avocatier']['annual_m3_ha']
        self.assertGreaterEqual(r['annual_gross_m3_ha'], lo)
        self.assertLessEqual(r['annual_gross_m3_ha'], hi)

    def test_myrtille_peak_near_cited_80(self):
        r = a.monthly_water_demand(
            crop='myrtille', region='gharb-loukkos', surface_ha=1, method='goutte')
        self.assertEqual(r['peak_m3_ha_day'], 75.8)  # parité JS
        self.assertGreaterEqual(r['peak_m3_ha_day'], 60)
        self.assertLessEqual(r['peak_m3_ha_day'], 100)

    def test_dattier_cited_per_tree(self):
        self.assertEqual(a.date_palm_cited_per_tree(), 51)
        self.assertIn('2026-07-16', a.CROP_CITED['dattier']['source'])
        self.assertEqual(a.CROP_CITED['dattier']['trees_per_ha'], 100)


class TestKcVectorsParity(SimpleTestCase):
    """Vecteurs Kc mensuels canoniques — IDENTIQUES au test JS."""

    def test_amandier(self):
        self.assertEqual(
            a.crop_kc_monthly('amandier'),
            [0, 0, 0.4, 0.65, 0.9, 0.9, 0.9, 0.9, 0.9, 0.817, 0.733, 0])

    def test_cereales(self):
        self.assertEqual(
            a.crop_kc_monthly('cereales'),
            [0.9, 1.15, 1.15, 0.775, 0, 0, 0, 0, 0, 0, 0.4, 0.65])

    def test_avocatier_evergreen(self):
        self.assertEqual(a.crop_kc_monthly('avocatier'), [0.85] * 12)


class TestAnnualIntegral(SimpleTestCase):
    def test_integral_replaces_flat_annualisation(self):
        r = a.monthly_water_demand(
            crop='avocatier', region='gharb-loukkos', surface_ha=1, method='goutte')
        self.assertEqual(a.annual_water_from_monthly(r), 10082)  # parité JS

    def test_invalid_returns_zero(self):
        self.assertEqual(a.annual_water_from_monthly(None), 0)
        self.assertEqual(a.annual_water_from_monthly({}), 0)


class TestSourcesAndCoverage(SimpleTestCase):
    def test_new_regions_present(self):
        self.assertEqual(len(a.ET0_MONTHLY['gharb-loukkos']), 12)
        self.assertEqual(len(a.ET0_MONTHLY['haouz']), 12)
        self.assertEqual(len(a.RAIN_EFF_MONTHLY['gharb-loukkos']), 12)

    def test_cannabis_flagged_estimated(self):
        self.assertTrue(a.CROP_STAGES['cannabis'].get('kc_estimated'))

    def test_table_covers_16_plus_crops(self):
        self.assertGreaterEqual(len(a.CROP_STAGES), 16)
