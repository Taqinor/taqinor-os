"""Tests AANA46 — litteraux d'etape (dict, comparaison, stage='X') dans
scripts/check_stages.py.

Stdlib pure (unittest), sans Django ni base. Run:
    python -m unittest scripts.tests.test_check_stages_litteraux -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_stages as cs  # noqa: E402


class TestLitterauxEtape(unittest.TestCase):
    def test_dict_et_comparaison_detectes(self):
        self.assertEqual(cs.count_literal_uses("W = {'NEW': 0.1}"), 1)
        self.assertEqual(
            cs.count_literal_uses("W = {\n    'SIGNED': 1,\n    \"COLD\": 0}"), 2)
        self.assertEqual(cs.count_literal_uses("if s == 'SIGNED':"), 1)
        self.assertEqual(cs.count_literal_uses("if s != \"COLD\":"), 1)
        self.assertEqual(cs.count_literal_uses("if 'SIGNED' == s:"), 1)
        self.assertEqual(cs.count_literal_uses("qs.filter(stage='SIGNED')"), 1)

    def test_formes_correctes_ne_rougissent_pas(self):
        self.assertEqual(cs.count_literal_uses("W = {stages.NEW: 0.1}"), 0)
        self.assertEqual(cs.count_literal_uses("if s == stages.SIGNED:"), 0)
        self.assertEqual(cs.count_literal_uses("qs.filter(stage=stages.NEW)"), 0)
        # Hors vocabulaire d'etape.
        self.assertEqual(cs.count_literal_uses("d = {'OTHER': 1}"), 0)
        self.assertEqual(cs.count_literal_uses("canal = 'NEW'"), 0)

    def test_plafond_depasse_rougit(self):
        # Test-du-test : au-dessus du plafond (ou fichier non liste) => rouge.
        f = cs.literal_failures({"a.py": 2}, {"a.py": 1})
        self.assertEqual(len(f), 1)
        self.assertIn("a.py", f[0])
        self.assertEqual(len(cs.literal_failures({"b.py": 1}, {})), 1)

    def test_plafond_egal_ou_vide_vert(self):
        self.assertEqual(cs.literal_failures({"a.py": 1}, {"a.py": 1}), [])
        self.assertEqual(cs.literal_failures({}, {}), [])

    def test_exception_morte_rougit(self):
        f = cs.literal_failures({}, {"a.py": 1})
        self.assertEqual(len(f), 1)
        self.assertIn("lower LITERAL_ALLOW", f[0])

    def test_plafonds_reels_declares(self):
        # Les plafonds figes pointent des fichiers existants.
        for rel in cs.LITERAL_ALLOW:
            self.assertTrue((ROOT / rel).exists(), rel)


class TestLitterauxEtapeJs(unittest.TestCase):
    """ADEP23 - litteraux d'etape cote frontend (js/jsx), hors stages.js et tests."""

    def test_js_comparaison_rouge(self):
        self.assertEqual(cs.count_js_literal_uses("if (stage === 'SIGNED') {}"), 1)
        self.assertEqual(cs.count_js_literal_uses('x = a !== "COLD"'), 1)
        self.assertEqual(cs.count_js_literal_uses("if ('NEW' == s) {}"), 1)
        self.assertEqual(cs.count_js_literal_uses(
            "stage === 'SIGNED' || stage === 'QUOTE_SENT'"), 2)

    def test_js_cle_nue_rouge(self):
        self.assertEqual(cs.count_js_literal_uses("const P = {\n  NEW: 0.1,\n  SIGNED: 1,\n}"), 2)
        self.assertEqual(cs.count_js_literal_uses("const P = { NEW: 0.1, COLD: 0 }"), 2)

    def test_js_cle_guillemets_rouge(self):
        self.assertEqual(cs.count_js_literal_uses("const P = { 'NEW': 0.1, \"SIGNED\": 1 }"), 2)

    def test_js_liste_rouge(self):
        self.assertEqual(cs.count_js_literal_uses(
            "const FUNNEL = ['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED']"), 1)
        self.assertEqual(cs.count_js_literal_uses("const A = ['NEW']"), 0)

    def test_formes_correctes_js_vertes(self):
        self.assertEqual(cs.count_js_literal_uses("if (stage === STAGES.SIGNED) {}"), 0)
        self.assertEqual(cs.count_js_literal_uses("const P = { [STAGES.NEW]: 0.1 }"), 0)
        self.assertEqual(cs.count_js_literal_uses("const l = a ? NEW : b"), 0)

    def test_stages_js_exempt(self):
        self.assertIn("frontend/src/features/crm/stages.js", cs.JS_LITERAL_EXEMPT)

    def test_plafond_fige_kanban(self):
        allow = cs.load_js_allow()
        self.assertEqual(allow["frontend/src/pages/crm/leads/views/KanbanView.jsx"], 6)
        for rel in allow:
            self.assertTrue((ROOT / rel).exists(), rel)
        self.assertEqual(len(cs.js_literal_failures({"a.jsx": 1}, {})), 1)
        self.assertEqual(len(cs.js_literal_failures({}, {"a.jsx": 1})), 1)
        self.assertEqual(cs.js_literal_failures({"a.jsx": 1}, {"a.jsx": 1}), [])

    def test_depot_reel_respecte_la_base_js(self):
        self.assertEqual(cs.js_literal_failures(cs.scan_js_literals(), cs.load_js_allow()), [])


if __name__ == "__main__":
    unittest.main()
