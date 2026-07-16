"""ADSENG24 — Tests des gabarits de lancement (dd-treasury §c).

Prouve : les 3 gabarits sont seedés (registre) avec un marché/objectif du
vocabulaire fermé, un budget défaut SOUS le plafond quotidien, et des slots
créatifs alignés sur ``CreativeAsset.AssetType`` ; la validation de slots
détecte les manques contre la bibliothèque validée policy ; et un lancement à
blanc produit la structure attendue dont CHAQUE objet est PAUSED (règle #3)."""
import datetime

from django.test import TestCase

from authentication.models import Company
from apps.adsengine import identity, launch_templates
from apps.adsengine.models import CreativeAsset

# Plafond quotidien défaut d'une ``GuardrailConfig`` (ENG3).
DEFAULT_DAILY_CEILING_MAD = 100


class TemplateRegistryTests(TestCase):
    def test_three_templates_seeded(self):
        keys = {t['key'] for t in launch_templates.list_templates()}
        self.assertEqual(
            keys, {'resid_ctwa', 'agri_pompage', 'b2b_leadform'})

    def test_market_and_objective_are_closed_vocabulary(self):
        for key in ('resid_ctwa', 'agri_pompage', 'b2b_leadform'):
            tpl = launch_templates.get_template(key)
            self.assertIn(tpl['market'], identity.MARKETS)
            self.assertIn(tpl['objective'], identity.OBJECTIVES)

    def test_default_budget_under_daily_ceiling(self):
        for key in ('resid_ctwa', 'agri_pompage', 'b2b_leadform'):
            tpl = launch_templates.get_template(key)
            total = sum(tpl['default_budget_split_mad'])
            self.assertLessEqual(
                total, DEFAULT_DAILY_CEILING_MAD,
                f'{key}: budget défaut {total} > plafond')
            # Nombre de splits cohérent avec la borne haute d'ad sets.
            self.assertLessEqual(
                len(tpl['default_budget_split_mad']), tpl['num_adsets'][1])

    def test_slot_keys_match_creative_asset_types(self):
        valid_types = {c[0] for c in CreativeAsset.AssetType.choices}
        for key in ('resid_ctwa', 'agri_pompage', 'b2b_leadform'):
            tpl = launch_templates.get_template(key)
            for slot_type in tpl['creative_slots']:
                self.assertIn(slot_type, valid_types)

    def test_abo_and_enhancements_off_for_no_fake_footage(self):
        for key in ('resid_ctwa', 'agri_pompage', 'b2b_leadform'):
            tpl = launch_templates.get_template(key)
            self.assertEqual(tpl['budget_optimization'], launch_templates.ABO)
            self.assertFalse(tpl['creative_enhancements'])

    def test_agricole_is_seasonal_and_has_no_reel(self):
        tpl = launch_templates.get_template('agri_pompage')
        self.assertTrue(tpl['seasonal'])
        self.assertNotIn(launch_templates.SLOT_REEL, tpl['creative_slots'])

    def test_get_unknown_template_raises(self):
        with self.assertRaises(ValueError):
            launch_templates.get_template('nope')

    def test_get_returns_a_copy(self):
        tpl = launch_templates.get_template('resid_ctwa')
        tpl['creative_slots']['reel'] = 99
        fresh = launch_templates.get_template('resid_ctwa')
        self.assertEqual(fresh['creative_slots']['reel'], 1)


class SlotValidationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Sv', slug='sv')

    def _asset(self, asset_type, *, passed=True):
        return CreativeAsset.objects.create(
            company=self.company, asset_type=asset_type,
            policy_stamp={'passed': True} if passed else {})

    def test_missing_slots_detected(self):
        tpl = launch_templates.get_template('resid_ctwa')
        ok, missing = launch_templates.validate_slots(tpl, {'reel': 1})
        self.assertFalse(ok)
        self.assertEqual(missing, {'static': 1, 'explainer': 1})

    def test_all_slots_present(self):
        tpl = launch_templates.get_template('resid_ctwa')
        ok, missing = launch_templates.validate_slots(
            tpl, {'reel': 2, 'static': 1, 'explainer': 3})
        self.assertTrue(ok)
        self.assertEqual(missing, {})

    def test_for_company_counts_only_policy_passed(self):
        self._asset('reel', passed=True)
        self._asset('static', passed=True)
        self._asset('explainer', passed=False)  # non validé → ne compte pas
        ok, missing = launch_templates.validate_slots_for_company(
            self.company, 'resid_ctwa')
        self.assertFalse(ok)
        self.assertEqual(missing, {'explainer': 1})


class DryRunTests(TestCase):
    def test_dry_run_structure_is_all_paused(self):
        result = launch_templates.dry_run_launch(
            'resid_ctwa', city='Casablanca',
            launch_date=datetime.date(2026, 7, 16), variant='A')
        self.assertEqual(result['template'], 'resid_ctwa')
        self.assertEqual(
            result['campaign']['name'], 'TQ-20260716-resid-ctwa-casablanca-a')
        self.assertEqual(result['campaign']['objective'], 'ctwa')
        # RÈGLE #3 : campagne ET chaque ad set naissent PAUSED.
        self.assertEqual(result['campaign']['status'], 'PAUSED')
        self.assertTrue(result['adsets'])
        for adset in result['adsets']:
            self.assertEqual(adset['status'], 'PAUSED')
        # 3 ad sets = 3 splits du gabarit résidentiel.
        self.assertEqual(len(result['adsets']), 3)
        self.assertEqual(result['utm']['utm_campaign'], 'resid_ctwa_casablanca_a')

    def test_dry_run_budgets_under_ceiling(self):
        result = launch_templates.dry_run_launch(
            'resid_ctwa', city='Rabat',
            launch_date=datetime.date(2026, 7, 16), variant='b')
        total = sum(a['daily_budget_mad'] for a in result['adsets'])
        self.assertLessEqual(total, DEFAULT_DAILY_CEILING_MAD)

    def test_dry_run_total_override_scales_split(self):
        result = launch_templates.dry_run_launch(
            'b2b_leadform', city='Tanger',
            launch_date=datetime.date(2026, 7, 16), variant='a',
            total_daily_budget_mad=40)
        total = sum(a['daily_budget_mad'] for a in result['adsets'])
        self.assertAlmostEqual(total, 40.0, places=2)
        for adset in result['adsets']:
            self.assertEqual(adset['status'], 'PAUSED')
