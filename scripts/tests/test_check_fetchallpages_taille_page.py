"""APRF29 — scripts/check_fetchallpages_taille_page.py (fixtures temporaires,
exécution réelle du script en sous-processus).

    python -m unittest scripts.tests.test_check_fetchallpages_taille_page -v
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "check_fetchallpages_taille_page.py"
sys.path.insert(0, str(ROOT / "scripts"))

import check_fetchallpages_taille_page as guard  # noqa: E402 — après sys.path (D-ENF22)


class _Arbre(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.front = self.racine / "frontend" / "src" / "pages"
        self.front.mkdir(parents=True)

    def ecrire(self, nom, src):
        (self.front / nom).write_text(textwrap.dedent(src), encoding="utf-8")

    def lancer(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--racine", str(self.racine)],
            capture_output=True, stdin=subprocess.DEVNULL,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


SANS_TAILLE = """\
    export function charger() {
      return fetchAllPages((page) => api.getX({ page }).then((r) => r.data))
    }
"""


class GardeTests(_Arbre):
    def test_appel_sans_page_size_echoue_et_nomme_fichier_ligne(self):
        self.ecrire("Ecran.jsx", SANS_TAILLE)
        code, out = self.lancer()
        self.assertEqual(code, 1, out)
        self.assertIn("pages/Ecran.jsx:2", out)

    def test_meme_appel_avec_page_size_passe(self):
        self.ecrire("Ecran.jsx", """\
            export const charger = () => fetchAllPages(
              (page, { page_size: pageSize } = {}) =>
                api.getX({ page, page_size: pageSize }).then((r) => r.data))
        """)
        code, out = self.lancer()
        self.assertEqual(code, 0, out)

    def test_page_size_litteral_passe(self):
        self.ecrire("Ecran.jsx", """\
            const a = fetchAllPages((page) => api.getX({ page, page_size: 200 }))
        """)
        self.assertEqual(self.lancer()[0], 0)

    def test_second_argument_repandu_passe(self):
        self.ecrire("Ecran.jsx", """\
            const a = fetchAllPages((page, o) => api.getX({ page, ...o }).then((r) => r.data))
        """)
        self.assertEqual(self.lancer()[0], 0)

    def test_second_argument_non_repandu_echoue(self):
        self.ecrire("Ecran.jsx", """\
            const a = fetchAllPages((page, o) => api.getX({ page }).then((r) => r.data))
        """)
        self.assertEqual(self.lancer()[0], 1)

    def test_commentaire_et_tests_ignores(self):
        self.ecrire("Ecran.jsx", """\
            // fetchAllPages((page) => api.getX({ page }))
            const a = 1
        """)
        self.ecrire("Ecran.test.jsx", SANS_TAILLE)
        code, out = self.lancer()
        self.assertEqual(code, 0, out)


class ExceptionsTests(_Arbre):
    def test_exception_datee_tolere_puis_perime(self):
        self.ecrire("Ecran.jsx", SANS_TAILLE)
        rel = "frontend/src/pages/Ecran.jsx"
        erreurs, _ = guard.evaluer(self.racine, {rel: ("2026-10-26", "motif", 1)})
        self.assertEqual(erreurs, [])
        # Un second appel fautif n'est pas couvert.
        self.ecrire("Ecran.jsx", SANS_TAILLE + SANS_TAILLE)
        erreurs, _ = guard.evaluer(self.racine, {rel: ("2026-10-26", "motif", 1)})
        self.assertEqual(len(erreurs), 1)
        # Appel corrigé : l'exception est périmée.
        self.ecrire("Ecran.jsx", "const a = 1\n")
        erreurs, _ = guard.evaluer(self.racine, {rel: ("2026-10-26", "motif", 1)})
        self.assertTrue(any("périmée" in e for e in erreurs), erreurs)

    def test_exception_sans_date_ou_sans_raison_echoue(self):
        self.ecrire("Ecran.jsx", SANS_TAILLE)
        rel = "frontend/src/pages/Ecran.jsx"
        self.assertTrue(guard.evaluer(self.racine, {rel: ("hier", "motif", 1)})[0])
        self.assertTrue(guard.evaluer(self.racine, {rel: ("2026-10-26", " ", 1)})[0])


class ArbreRealTests(unittest.TestCase):
    def test_depot_courant_vert(self):
        erreurs, _ = guard.evaluer(guard.ROOT, guard.EXCEPTIONS)
        self.assertEqual(erreurs, [])


if __name__ == "__main__":
    unittest.main()
