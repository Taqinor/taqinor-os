"""APAR65 - scripts/check_page_size_front.py (fixtures JSX + plafond lu)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_page_size_front as guard  # noqa: E402

TRONQUE = """
export function charger() {
  return api.get('/x/', { params: { page_size: 500 } }).then((r) => setRows(r.data.results))
}
"""
GRANDE_PAGE_MILLE = TRONQUE.replace("500", "1000")
SOUS_LE_PLAFOND = TRONQUE.replace("500", "200")
AVEC_HELPER = """
export function charger() {
  return fetchAllPages((p) => api.get('/x/', { params: { page_size: 1000, page: p } })
    .then((r) => r.data)).then((rows) => setRows(rows.results ?? rows))
}
"""
SANS_RESULTS = """
export function compter() {
  return api.get('/x/', { params: { page_size: 1000 } }).then((r) => r.data.count)
}
"""


class PageSizeFrontTests(unittest.TestCase):
    def test_plafond_lu_dans_le_code_serveur(self):
        self.assertEqual(guard.plafond(), 200)

    def test_page_size_au_dessus_du_plafond_rouge(self):
        for source in (TRONQUE, GRANDE_PAGE_MILLE):
            trouves = guard.analyser_source(source, 200)
            self.assertEqual(list(trouves), ["charger"])
            self.assertTrue(guard.verifier({"a.jsx::charger": 3}, {}, 200))

    def test_abaisser_la_detection_a_1000_laisse_passer_le_cas_500(self):
        # test-du-test : un seuil de detection a 1000 ne verrait pas le cas 500
        self.assertEqual(guard.analyser_source(TRONQUE, 1000), {})

    def test_sous_le_plafond_helper_ou_sans_results_vert(self):
        for source in (SOUS_LE_PLAFOND, AVEC_HELPER, SANS_RESULTS):
            self.assertEqual(guard.analyser_source(source, 200), {})

    def test_dette_gelee_et_entree_morte(self):
        trouves = {"a.jsx::charger": 3}
        self.assertEqual(guard.verifier(trouves, {"a.jsx::charger": "r"}, 200), [])
        erreurs = guard.verifier({}, {"a.jsx::charger": "r"}, 200)
        self.assertTrue(any("MORTE" in e for e in erreurs))

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(guard.analyser(), max_ps=guard.plafond()), [])


if __name__ == "__main__":
    unittest.main()
