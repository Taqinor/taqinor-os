"""Tests ADOC147 — scripts/check_portail_surfaces.py.

Stdlib pure (unittest), aucune base. Run :
    python -m unittest scripts.tests.test_check_portail_surfaces -v
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_portail_surfaces as guard  # noqa: E402

URLS = """
router.register(r'mes-documents', MesDocumentsViewSet, basename='x')
router.register(r'mes-demandes-sav', MesDemandesSavViewSet, basename='y')
router.register(r'comptes-portail', ComptesViewSet, basename='z')
urlpatterns = [
    path('client/ma-consommation/', ma_consommation, name='c'),
    path('', include(router.urls)),
]
"""

API = """
const portailApi = {
  documents: {
    liste: () => api.get('/portail/mes-documents/'),
  },
  consommation: (params) =>
    api.get('/portail/client/ma-consommation/', { params }),
  demandesSav: {
    liste: () => api.get('/portail/mes-demandes-sav/'),
  },
}
export default portailApi
"""

ECRAN = """
import portailApi from '../../api/portailApi'
portailApi.documents.liste()
portailApi.consommation({})
portailApi.demandesSav.liste()
"""


class Depot(unittest.TestCase):
    def _monter(self, urls=URLS, api=API, ecrans=None, allow=""):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "backend" / "django_core" / "apps" / "portail").mkdir(parents=True)
        (tmp / "frontend" / "src" / "api").mkdir(parents=True)
        feat = tmp / "frontend" / "src" / "features" / "portail"
        feat.mkdir(parents=True)
        (tmp / "scripts").mkdir()
        (tmp / "backend/django_core/apps/portail/urls.py").write_text(
            urls, encoding="utf-8")
        (tmp / "frontend/src/api/portailApi.js").write_text(api, encoding="utf-8")
        for nom, contenu in (ecrans if ecrans is not None
                             else {"Ecran.jsx": ECRAN}).items():
            (feat / nom).write_text(contenu, encoding="utf-8")
        (tmp / "scripts/portail_surfaces_allow.txt").write_text(
            allow, encoding="utf-8")
        sauve = (guard.URLS_PATH, guard.API_PATH, guard.FEATURES_DIR,
                 guard.ALLOWLIST_PATH)
        guard.URLS_PATH = tmp / "backend/django_core/apps/portail/urls.py"
        guard.API_PATH = tmp / "frontend/src/api/portailApi.js"
        guard.FEATURES_DIR = feat
        guard.ALLOWLIST_PATH = tmp / "scripts/portail_surfaces_allow.txt"

        def restaurer():
            (guard.URLS_PATH, guard.API_PATH, guard.FEATURES_DIR,
             guard.ALLOWLIST_PATH) = sauve
        self.addCleanup(restaurer)

    @staticmethod
    def _main():
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = guard.main()
        return code, buf.getvalue()


class TestSurfaces(Depot):
    def test_routes_self_service_seules(self):
        self.assertEqual(
            guard.routes_self_service(URLS),
            ["mes-documents", "mes-demandes-sav", "client/ma-consommation"])

    def test_tout_branche_est_vert(self):
        self._monter()
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_route_sans_ecran_rougit_en_la_nommant(self):
        # On retire l'ecran « Documents » : la route reste sans utilisateur.
        self._monter(ecrans={"Ecran.jsx": ECRAN.replace(
            "portailApi.documents.liste()", "")})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("mes-documents", out)

    def test_nouvelle_route_mes_sans_appelant_rougit(self):
        self._monter(urls=URLS + "router.register(r'mes-nouveautes', V, basename='n')\n")
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("mes-nouveautes", out)
        self.assertIn("aucun appelant dans portailApi.js", out)

    def test_api_declaree_mais_jamais_appelee(self):
        # Test-du-test : si la recherche d'appelant dans features/portail etait
        # neutralisee, ce cas passerait a tort.
        self._monter(ecrans={"Ecran.jsx": ECRAN.replace(
            "portailApi.demandesSav.liste()", "")})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("mes-demandes-sav", out)
        self.assertIn("jamais utilisé par un écran", out)

    def test_un_fichier_de_test_ne_compte_pas_comme_ecran(self):
        self._monter(ecrans={"Ecran.test.jsx": ECRAN})
        code, out = self._main()
        self.assertEqual(code, 1, out)

    def test_allowlist_tolere_une_surface_gated(self):
        self._monter(ecrans={"Ecran.jsx": ECRAN.replace(
            "portailApi.demandesSav.liste()", "")},
            allow="mes-demandes-sav\n")
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_ligne_devenue_inutile_fait_echouer(self):
        self._monter(allow="mes-demandes-sav\n")
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("INUTILES", out)


class TestDepotReel(unittest.TestCase):
    def test_depot_reel_vert(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = guard.main()
        self.assertEqual(code, 0, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
