"""ADSENG37 — Tests des constantes de config des inconnues terrain.

Prouve : les 7 micro-tests (FT1..FT7) couvrent toutes les constantes ; les valeurs
sont câblées EN CONFIG (pas en dur) et accessibles ; les inconnues non encore
tranchées restent marquées « recherche » (dry — premier test documenté à blanc) ;
les garde-fous du protocole (budget plafonné, PAUSED d'abord, un facteur) existent.
"""
import pathlib

from django.test import SimpleTestCase

from apps.adsengine import field_tests as ft


class FieldTestConstantsTests(SimpleTestCase):
    def test_seven_field_tests_declared(self):
        self.assertEqual(len(ft.FIELD_TESTS), 7)
        self.assertEqual(
            set(ft.FIELD_TESTS),
            {'FT1', 'FT2', 'FT3', 'FT4', 'FT5', 'FT6', 'FT7'})

    def test_every_constant_maps_to_a_declared_field_test(self):
        for key, meta in ft.CONSTANTS.items():
            self.assertIn(meta['ft'], ft.FIELD_TESTS,
                          f'{key} référence un micro-test inconnu')
            # Chaque constante déclare son consommateur (traçabilité du câblage).
            self.assertTrue(meta.get('consumer'))
            self.assertTrue(meta.get('label_fr'))

    def test_each_field_test_resolves_at_least_one_constant(self):
        for ftid in ft.FIELD_TESTS:
            self.assertTrue(
                ft.constants_for(ftid),
                f'{ftid} ne résout aucune constante')

    def test_all_unknowns_start_as_research_dry(self):
        # Premier test documenté À BLANC : aucune constante n'est encore
        # confirmée terrain — toutes en source=recherche.
        for key in ft.CONSTANTS:
            self.assertFalse(ft.is_field_tested(key), key)
        self.assertEqual(sorted(ft.pending_keys()), sorted(ft.CONSTANTS.keys()))

    def test_values_are_config_driven_accessors(self):
        # Les valeurs se lisent par accesseur (câblage config, pas en dur).
        self.assertEqual(ft.value('learning_reset_budget_pct'), 20)
        self.assertEqual(ft.value('buc_write_cost_points'), 3)
        self.assertIsNone(ft.value('even_rotation_api_settable'))
        with self.assertRaises(KeyError):
            ft.value('inconnue')

    def test_micro_test_safety_guards_present(self):
        # Budget plafonné + PAUSED d'abord + un facteur à la fois.
        self.assertLessEqual(ft.MICRO_TEST_MAX_DAILY_BUDGET_MAD, 50)
        self.assertEqual(ft.micro_test_budget_cap_mad(),
                         ft.MICRO_TEST_MAX_DAILY_BUDGET_MAD)
        self.assertTrue(ft.MICRO_TEST_START_PAUSED)
        self.assertTrue(ft.MICRO_TEST_ONE_FACTOR_AT_A_TIME)


class FieldTestRunbookTests(SimpleTestCase):
    def _runbook(self):
        # .../backend/django_core/apps/adsengine/tests/<file> → repo root = [5].
        root = pathlib.Path(__file__).resolve().parents[5]
        return root / 'docs' / 'engine' / 'field-tests.md'

    def test_runbook_committed_and_covers_seven_tests(self):
        path = self._runbook()
        self.assertTrue(path.exists(), 'docs/engine/field-tests.md manquant')
        text = path.read_text(encoding='utf-8')
        for ftid in ft.FIELD_TESTS:
            self.assertIn(f'## {ftid}', text, f'{ftid} absent du runbook')
        # Garde-fous de sécurité documentés (PAUSED d'abord, budget plafonné).
        self.assertIn('PAUSED', text)
        self.assertIn('MICRO_TEST_MAX_DAILY_BUDGET_MAD', text)
