"""Tests ADOC38 — scripts/check_liste_page1.py (classe « liste lue page 1 »).

Stdlib pure (unittest), aucune base. Run :
    python -m unittest scripts.tests.test_check_liste_page1 -v
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_liste_page1 as guard  # noqa: E402

PAGE1 = """
import api from '../../api/axios'

export default function ComptesPortailAdmin() {
  const charger = () => {
    api.get('/portail/comptes/').then((r) => setRows(r.data?.results ?? []))
  }
  return null
}
"""

TOUTES_LES_PAGES = """
import { fetchAllPages } from '../../utils/fetchAllPages'

export default function Liste() {
  const charger = async () => {
    const rows = await fetchAllPages((p) => api.get('/x/', { params: { page: p } })
      .then((r) => r.data))
    setRows(rows)
  }
  return null
}
"""

LIT_NEXT = """
export default function Liste() {
  const charger = async () => {
    const r = await api.get('/x/')
    setRows(r.data?.results ?? [])
    setSuite(r.data?.next)
  }
  return null
}
"""

NON_PAGINE = """
export default function Liste() {
  const charger = async () => {
    const r = await api.get('/portail/tout-en-un/')
    setRows(r.data?.results ?? [])
  }
  return null
}
"""

BACKEND_NON_PAGINE_VIEWS = """
from rest_framework import viewsets


class ToutEnUnViewSet(viewsets.ModelViewSet):
    pagination_class = None
"""

BACKEND_NON_PAGINE_URLS = """
router.register(r'tout-en-un', ToutEnUnViewSet, basename='tout-en-un')
"""


HELPER_UNPAGE = """
function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

export default function Coffres() {
  const load = async () => {
    const c = await gedApi.getCoffres()
    setCoffres(unpage(c.data))
  }
  return null
}
"""

HELPER_TOUTES_LES_PAGES = HELPER_UNPAGE.replace(
    "gedApi.getCoffres()", "toutesLesPages(gedApi.getCoffres)")


class Depot(unittest.TestCase):
    def _monter(self, fichiers, backend=None, allow="", dossier="features"):
        tmp = Path(tempfile.mkdtemp())
        feat = tmp / "frontend" / "src" / "features"
        for nom, contenu in fichiers.items():
            cible = tmp / "frontend" / "src" / dossier / nom
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(contenu, encoding="utf-8")
        be = tmp / "backend" / "django_core" / "apps" / "portail"
        be.mkdir(parents=True)
        for nom, contenu in (backend or {}).items():
            (be / nom).write_text(contenu, encoding="utf-8")
        (tmp / "scripts").mkdir()
        (tmp / "scripts" / "liste_page1_allow.txt").write_text(
            allow, encoding="utf-8")
        sauve = (guard.ROOT, guard.FRONTEND_FEATURES, guard.BACKEND,
                 guard.ALLOWLIST_PATH)
        guard.ROOT = tmp
        guard.FRONTEND_FEATURES = feat
        guard.BACKEND = tmp / "backend" / "django_core"
        guard.ALLOWLIST_PATH = tmp / "scripts" / "liste_page1_allow.txt"

        def restaurer():
            (guard.ROOT, guard.FRONTEND_FEATURES, guard.BACKEND,
             guard.ALLOWLIST_PATH) = sauve
        self.addCleanup(restaurer)

    @staticmethod
    def _main():
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = guard.main([])
        return code, buf.getvalue()


class TestDetection(Depot):
    def test_detecte_lecture_page1(self):
        self._monter({"portail/ComptesPortailAdmin.jsx": PAGE1})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("ComptesPortailAdmin.jsx", out)
        self.assertIn("lit la page 1 d'une liste paginée", out)
        self.assertIn("utils/fetchAllPages", out)

    def test_detecte_helper_unpage(self):
        self._monter({"ged/Coffres.jsx": HELPER_UNPAGE})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("Coffres.jsx", out)
        self.assertIn("load lit la page 1", out)

    def test_helper_unpage_avec_toutes_les_pages_ne_rougit_pas(self):
        self._monter({"ged/Coffres.jsx": HELPER_TOUTES_LES_PAGES})
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_fetch_all_pages_ou_next_ne_rougit_pas(self):
        self._monter({"a/Liste.jsx": TOUTES_LES_PAGES,
                      "b/Liste.jsx": LIT_NEXT})
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_endpoint_non_pagine_derive_du_code_exclu(self):
        self._monter(
            {"a/Liste.jsx": NON_PAGINE},
            backend={"views.py": BACKEND_NON_PAGINE_VIEWS,
                     "urls.py": BACKEND_NON_PAGINE_URLS})
        self.assertEqual(guard.segments_non_pagines(), {"tout-en-un"})
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_meme_endpoint_pagine_rougit(self):
        # Sans pagination_class = None cote serveur, l'exclusion disparait.
        self._monter({"a/Liste.jsx": NON_PAGINE})
        code, out = self._main()
        self.assertEqual(code, 1, out)

    def test_les_tests_sont_ignores(self):
        self._monter({"a/Liste.test.jsx": PAGE1})
        code, out = self._main()
        self.assertEqual(code, 0, out)


class TestAllowlist(Depot):
    CLE = "frontend/src/features/portail/ComptesPortailAdmin.jsx::charger"

    def test_allowlist_par_contenu_tolere_le_site(self):
        self._monter({"portail/ComptesPortailAdmin.jsx": PAGE1}, allow=self.CLE + "\n")
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_cle_morte_fait_echouer(self):
        self._monter({"portail/ComptesPortailAdmin.jsx": TOUTES_LES_PAGES},
                     allow=self.CLE + "\n")
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("MORTES", out)

    def test_la_cle_ne_depend_pas_du_numero_de_ligne(self):
        decale = "// commentaire\n// commentaire\n" + PAGE1
        self._monter({"portail/ComptesPortailAdmin.jsx": decale},
                     allow=self.CLE + "\n")
        code, out = self._main()
        self.assertEqual(code, 0, out)


SLICE = """
import { createAsyncThunk } from '@reduxjs/toolkit'

export const fetchPaiements = createAsyncThunk('ventes/fetchPaiements', async () => {
  const response = await api.get('/ventes/paiements/')
  return response.data.results
})
"""


class PagesEtStoreTests(Depot):
    """AFAC95 : la garde voit aussi pages/** et store/**."""

    def test_page_lisant_results_signalee(self):
        self._monter({"ventes/PaiementsPage.jsx": PAGE1}, dossier="pages")
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("frontend/src/pages/ventes/PaiementsPage.jsx", out)

    def test_slice_store_signale(self):
        self._monter({"ventesSlice.js": SLICE}, dossier="store")
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("frontend/src/store/ventesSlice.js", out)
        self.assertIn("fetchPaiements", out)


class PagesTests(Depot):
    """ASAV77 : un nouvel écran de pages/ qui lit .results sans fetchAllPages."""

    def test_page_signalee(self):
        self._monter({"sav/Liste.jsx": PAGE1}, dossier="pages")
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("pages/sav/Liste.jsx", out)

    def test_fetch_all_pages_accepte(self):
        self._monter({"sav/Liste.jsx": TOUTES_LES_PAGES,
                      "sav/Suite.jsx": LIT_NEXT}, dossier="pages")
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_cle_morte_echoue(self):
        cle = "frontend/src/pages/sav/Liste.jsx::charger"
        self._monter({"sav/Liste.jsx": TOUTES_LES_PAGES}, allow=cle + chr(10),
                     dossier="pages")
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("MORTES", out)

    def test_page_gelee_dans_la_liste_ne_rougit_pas(self):
        cle = "frontend/src/pages/sav/Liste.jsx::charger"
        self._monter({"sav/Liste.jsx": PAGE1.replace("ComptesPortailAdmin", "Liste")},
                     allow=cle + chr(10), dossier="pages")
        code, out = self._main()
        self.assertEqual(code, 0, out)


class TestArbreReel(unittest.TestCase):
    def test_arbre_reel_vert(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = guard.main([])
        self.assertEqual(code, 0, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
