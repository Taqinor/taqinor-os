"""Tests FG390 — évaluateur de formules sûr (champ calculé FORMULA).

Couvre :
  * arithmétique, comparaisons, booléens, ternaire, fonctions sûres ;
  * variables de contexte ;
  * sécurité : appels arbitraires / attributs / imports / lambdas rejetés ;
  * division par zéro et variable inconnue maîtrisées (FormulaError) ;
  * validation de formule (variables connues + sûreté).
"""
from django.test import SimpleTestCase

from core.formula import FormulaError, evaluer_formule, valider_formule


class FormulaEvalTests(SimpleTestCase):
    def test_arithmetic(self):
        self.assertEqual(evaluer_formule('1 + 2 * 3'), 7)
        self.assertEqual(evaluer_formule('(prix_ht) * (1 + tva)',
                                         {'prix_ht': 100, 'tva': 0.2}), 120)

    def test_functions_and_ternary(self):
        self.assertEqual(evaluer_formule('max(a, b)', {'a': 3, 'b': 9}), 9)
        self.assertEqual(evaluer_formule('round(x, 2)', {'x': 1.23456}), 1.23)
        self.assertEqual(
            evaluer_formule('a if a > b else b', {'a': 1, 'b': 5}), 5)

    def test_comparisons_and_bool(self):
        self.assertTrue(evaluer_formule('1 < 2 <= 2'))
        self.assertTrue(evaluer_formule('x and y', {'x': True, 'y': 1}))

    def test_unknown_variable_raises(self):
        with self.assertRaises(FormulaError):
            evaluer_formule('inconnu + 1')

    def test_division_by_zero_raises(self):
        with self.assertRaises(FormulaError):
            evaluer_formule('1 / 0')

    def test_arbitrary_call_rejected(self):
        with self.assertRaises(FormulaError):
            evaluer_formule("__import__('os').system('echo hi')")

    def test_attribute_access_rejected(self):
        with self.assertRaises(FormulaError):
            evaluer_formule("(1).__class__")

    def test_lambda_rejected(self):
        with self.assertRaises(FormulaError):
            evaluer_formule('(lambda: 1)()')

    def test_huge_power_rejected(self):
        with self.assertRaises(FormulaError):
            evaluer_formule('2 ** 100000')


class FormulaValidationTests(SimpleTestCase):
    def test_valid_with_known_vars(self):
        ok, err = valider_formule('a + b', ['a', 'b'])
        self.assertTrue(ok, err)

    def test_invalid_unknown_var(self):
        ok, err = valider_formule('a + zzz', ['a'])
        self.assertFalse(ok)
        self.assertIn('zzz', err)

    def test_division_probe_is_valid(self):
        ok, err = valider_formule('a / b', ['a', 'b'])
        self.assertTrue(ok, err)
