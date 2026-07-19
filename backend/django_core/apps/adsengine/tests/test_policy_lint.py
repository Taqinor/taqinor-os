"""AGEN5 — Corpus rouge/vert du pré-linter policy/marque FR, règle par règle.

Prouve (dd-assumption-engine §10.2 point 4) : chaque catégorie de règle bloque
son motif interdit, le financier lève la catégorie spéciale sans bloquer, et un
texte propre passe. Les règles vivent en CONFIG (``policy_lint_config``).
"""
from django.test import SimpleTestCase

from apps.adsengine import policy_lint
from apps.adsengine.policy_lint_config import SPECIAL_CATEGORY_FINANCIAL


class PolicyLintGreenTests(SimpleTestCase):
    def test_clean_text_passes(self):
        result = policy_lint.lint_text(
            'Installation solaire clé en main, devis gratuit.')
        self.assertTrue(result['ok'])
        self.assertEqual(result['flags'], [])
        self.assertEqual(result['special_categories'], [])


class PolicyLintRedTests(SimpleTestCase):
    def _first(self, text):
        result = policy_lint.lint_text(text)
        return result

    def test_superlative_blocked(self):
        r = self._first('Le meilleur installateur solaire du Maroc.')
        self.assertFalse(r['ok'])
        self.assertTrue(any(f['category'] == 'superlatifs' for f in r['flags']))

    def test_numero_un_blocked(self):
        r = self._first('Solaire n°1 dans la région.')
        self.assertFalse(r['ok'])

    def test_personal_attribute_blocked(self):
        r = self._first('Parce que vous êtes au chômage, économisez.')
        self.assertFalse(r['ok'])
        self.assertTrue(
            any(f['category'] == 'attributs_personnels' for f in r['flags']))

    def test_before_after_blocked(self):
        r = self._first('Regardez le avant / après de nos toitures.')
        self.assertFalse(r['ok'])
        self.assertTrue(any(f['category'] == 'avant_apres' for f in r['flags']))

    def test_brand_decennale_blocked(self):
        r = self._first('Travaux couverts par une assurance décennale.')
        self.assertFalse(r['ok'])
        self.assertTrue(
            any(f['rule_id'] == 'marque_decennale' for f in r['flags']))

    def test_install_count_blocked(self):
        r = self._first('Déjà 250 installations réalisées au Maroc.')
        self.assertFalse(r['ok'])
        self.assertTrue(
            any(f['rule_id'] == 'marque_compte_installations'
                for f in r['flags']))

    def test_financial_flags_special_category_without_blocking(self):
        r = policy_lint.lint_text('Payez en 12 fois sans souci.')
        # Financier = drapeau, PAS bloquant.
        self.assertTrue(r['ok'])
        self.assertIn(SPECIAL_CATEGORY_FINANCIAL, r['special_categories'])
        self.assertTrue(any(f['action'] == 'flag' for f in r['flags']))

    def test_multiple_violations_all_reported(self):
        r = policy_lint.lint_text(
            'Le meilleur, avant / après, assurance décennale.')
        cats = {f['category'] for f in r['flags']}
        self.assertIn('superlatifs', cats)
        self.assertIn('avant_apres', cats)
        self.assertIn('marque', cats)
        self.assertFalse(r['ok'])
