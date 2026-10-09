"""Tests AACQ77 — scripts/check_adsengine_ecrans.py (écrans publicité).

Stdlib pure (unittest). Run :
    python -m unittest scripts.tests.test_check_adsengine_ecrans -v
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_adsengine_ecrans as guard  # noqa: E402

PAGE1 = """
export default function Ecran() {
  useEffect(() => {
    adsengineApi.items.list().then(r => setRows(r.data?.results || []))
  }, [])
  return null
}
"""

TOUTES_LES_PAGES = """
export default function Ecran() {
  useEffect(() => {
    fetchAllPages((page) => adsengineApi.items.list({ page }))
      .then(r => setRows(r.data?.results || []))
  }, [])
  return null
}
"""

CATCH_VIDE = """
export default function Ecran() {
  useEffect(() => {
    adsengineApi.stats().then(r => setStats(r.data)).catch(() => setStats([]))
  }, [])
  return null
}
"""

CATCH_AVEC_ERREUR = """
export default function Ecran() {
  useEffect(() => {
    adsengineApi.stats().then(r => setStats(r.data))
      .catch(() => { setStats([]); setLoadError(true) })
  }, [])
  return null
}
"""


class CheckAdsengineEcransTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.dossier = base / "frontend" / "src" / "features" / "adsengine"
        self.dossier.mkdir(parents=True)
        self.allow = base / "allow.txt"
        self._orig = (guard.ROOT, guard.ADSENGINE, guard.PAYLOADS,
                      guard.ALLOWLIST_PATH)
        guard.ROOT = base
        guard.ADSENGINE = self.dossier
        guard.PAYLOADS = base / "absent.jsx"
        guard.ALLOWLIST_PATH = self.allow

    def tearDown(self):
        (guard.ROOT, guard.ADSENGINE, guard.PAYLOADS,
         guard.ALLOWLIST_PATH) = self._orig
        self._tmp.cleanup()

    def _run(self, source):
        (self.dossier / "Ecran.jsx").write_text(source, encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = guard.main([])
        return code, out.getvalue()

    def test_page1_nue_rouge(self):
        code, sortie = self._run(PAGE1)
        self.assertEqual(code, 1)
        self.assertIn("Ecran.jsx:4", sortie)
        self.assertIn("page 1", sortie)

    def test_fetch_all_pages_vert(self):
        code, _ = self._run(TOUTES_LES_PAGES)
        self.assertEqual(code, 0)

    def test_catch_vide_rouge(self):
        code, sortie = self._run(CATCH_VIDE)
        self.assertEqual(code, 1)
        self.assertIn("Ecran.jsx:4", sortie)
        self.assertIn("état d'erreur", sortie)

    def test_catch_avec_etat_erreur_vert(self):
        code, _ = self._run(CATCH_AVEC_ERREUR)
        self.assertEqual(code, 0)

    def test_entree_gelee_vert(self):
        (self.dossier / "Ecran.jsx").write_text(CATCH_VIDE, encoding="utf-8")
        cle = next(iter(guard.analyser()))
        self.allow.write_text(cle + "\n", encoding="utf-8")
        code, _ = self._run(CATCH_VIDE)
        self.assertEqual(code, 0)

    def test_entree_gelee_devenue_conforme_rouge(self):
        (self.dossier / "Ecran.jsx").write_text(CATCH_VIDE, encoding="utf-8")
        cle = next(iter(guard.analyser()))
        self.allow.write_text(cle + "\n", encoding="utf-8")
        code, sortie = self._run(CATCH_AVEC_ERREUR)
        self.assertEqual(code, 1)
        self.assertIn("MORTES", sortie)


if __name__ == "__main__":
    unittest.main()
