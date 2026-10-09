"""Tests YDATA19 — scripts/check_db_invariants.py parser.

Pure stdlib (unittest), no Django. Run:
    python -m unittest scripts.tests.test_check_db_invariants -v
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_db_invariants as cdi  # noqa: E402


CLEAN_WITH_BOUND = '''
class Paiement:
    def clean(self):
        if self.montant < 0:
            raise ValidationError("neg")
'''

CROSS_FIELD = '''
class Facture:
    def clean(self):
        if self.total_ttc < self.total_ht:
            raise ValidationError("ttc<ht")
'''

WITH_CHECKCONSTRAINT = '''
class Paiement:
    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(montant__gte=0), name='p_pos'),
        ]
'''

NO_INVARIANT = '''
class Devis:
    def save(self, *a, **k):
        self.reference = "X"
'''


def _cls(src):
    return cdi._find_class(ast.parse(src), ast.parse(src).body[0].name)


class TestDbInvariants(unittest.TestCase):
    def test_clean_numeric_bound_detected(self):
        cls = _cls(CLEAN_WITH_BOUND)
        self.assertIn("montant", cdi.python_invariants(cls))

    def test_cross_field_invariant_detected(self):
        cls = _cls(CROSS_FIELD)
        fields = cdi.python_invariants(cls)
        self.assertIn("total_ttc", fields)
        self.assertIn("total_ht", fields)

    def test_checkconstraint_field_extracted(self):
        cls = _cls(WITH_CHECKCONSTRAINT)
        self.assertIn("montant", cdi.checkconstraint_fields(cls))

    def test_no_invariant_no_false_positive(self):
        cls = _cls(NO_INVARIANT)
        self.assertEqual(cdi.python_invariants(cls), set())

    def test_gap_when_bound_but_no_constraint(self):
        # A clean() with >= 0 but no CheckConstraint is the target gap.
        cls = _cls(CLEAN_WITH_BOUND)
        self.assertTrue(cdi.python_invariants(cls))
        self.assertEqual(cdi.checkconstraint_fields(cls), set())


class TestBlocking(unittest.TestCase):
    """ENF13 — l'outil échoue sur tout écart, vert sur le dépôt courant."""

    def test_depot_courant_sans_ecart(self):
        self.assertEqual(cdi.find_gaps(cdi.scan()), [])

    def test_invariant_canonique_non_contraint_est_un_ecart(self):
        rows = [("M", "app", set(), set(), ["quantite >= 0"])]
        self.assertEqual(len(cdi.find_gaps(rows)), 1)

    def test_invariant_python_seul_est_un_ecart(self):
        rows = [("M", "app", {"montant"}, set(), [])]
        self.assertEqual(len(cdi.find_gaps(rows)), 1)

    def test_contrainte_presente_est_vert(self):
        rows = [("M", "app", {"montant"}, {"montant"}, ["montant >= 0"])]
        self.assertEqual(cdi.find_gaps(rows), [])

    def test_classe_introuvable_non_parquee_est_un_ecart(self):
        rows = [("M", "app", set(), cdi._INTROUVABLE, ["x >= 0"])]
        self.assertEqual(len(cdi.find_gaps(rows)), 1)

    def test_app_parquee_n_est_pas_un_ecart(self):
        rows = [("LigneEcriture", "compta", set(), cdi._PARQUE, ["debit >= 0"])]
        self.assertEqual(cdi.find_gaps(rows), [])

    def test_compta_est_bien_parquee(self):
        self.assertTrue(cdi._app_parquee("compta"))
        self.assertFalse(cdi._app_parquee("stock"))

    def test_main_check_vert(self):
        self.assertEqual(cdi.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
