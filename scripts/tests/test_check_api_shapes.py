"""Tests de scripts/check_api_shapes.py (garde de FORME du 03/08/2026).

Stdlib pur (unittest), aucune base de donnees, aucun Django. Lancer :
    python -m unittest scripts.tests.test_check_api_shapes -v

Les deux tests les plus importants sont ceux qui empechent la garde de crier
au loup : elle a produit, en cours de calibrage, deux classes de faux positifs
(mock apparie par NOM a un autre module, et forme d'un GET opposee au mock
d'un POST) qui l'auraient rendue inutilisable.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_api_shapes as shapes  # noqa: E402
import check_api_contract as contract  # noqa: E402


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class ShapeReaderTests(unittest.TestCase):
    """Lecture du dictionnaire REELLEMENT renvoye par une vue."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        write(self.base / "erp_agentique" / "urls.py", """
from django.urls import include, path
urlpatterns = [path('api/django/', include([path('ao/', include('apps.ao.urls'))]))]
""")
        write(self.base / "apps" / "ao" / "urls.py", """
from django.urls import path
from .kpis import tableau_marches_view
urlpatterns = [path('tableau-marches/', tableau_marches_view)]
""")
        write(self.base / "apps" / "ao" / "kpis.py", """
from rest_framework.response import Response

def tableau_marches_view(request):
    from .selectors import tableau_marches
    return Response(tableau_marches(request.user.company))
""")
        write(self.base / "apps" / "ao" / "selectors.py", """
def _marches_en_execution(company):
    return {'total': 0, 'montant': 0}

def tableau_marches(company):
    return {
        'en_cours': _en_cours(company),
        'echeances_dues': len(echeances_ao_dues(company)),
        'marches_en_execution': _marches_en_execution(company),
        'libelle': 'texte',
    }

def _en_cours(company):
    return {'total': 0}
""")
        self.backend = contract.BackendRoutes(self.base)
        self.backend.build()
        self.reader = shapes.ShapeReader(self.backend)
        self.route = ("api", "django", "ao", "tableau-marches")

    def tearDown(self):
        self.tmp.cleanup()

    def test_forme_traversant_le_selecteur(self):
        # L'incident exact : la vue delegue au selecteur, il faut suivre.
        forme = self.reader.shape_of_route(self.route, "get")
        self.assertEqual(forme["en_cours"], shapes.OBJET)
        self.assertEqual(forme["marches_en_execution"], shapes.OBJET)
        self.assertEqual(forme["libelle"], shapes.TEXTE)

    def test_len_est_un_nombre_pas_une_liste(self):
        # `'echeances_dues': len(...)` -> le front faisait `.map()` dessus.
        self.assertEqual(self.reader.shape_of_route(self.route, "get")["echeances_dues"],
                         shapes.NOMBRE)

    def test_forme_incertaine_reste_hors_contrat(self):
        write(self.base / "apps" / "ao" / "selectors.py",
              "def tableau_marches(company):\n    return construire(company)\n")
        backend = contract.BackendRoutes(self.base)
        backend.build()
        reader = shapes.ShapeReader(backend)
        self.assertIsNone(reader.shape_of_route(self.route, "get"))

    def test_le_verbe_http_compte(self):
        # Faux positif mesure : une vue APIView renvoie `{presets}` en GET et
        # tout autre chose en POST. Apparier le mock d'un POST a la forme du
        # GET accusait du code CORRECT.
        write(self.base / "apps" / "ao" / "urls.py", """
from django.urls import path
from .kpis import AudienceView
urlpatterns = [path('audiences/', AudienceView.as_view())]
""")
        write(self.base / "apps" / "ao" / "kpis.py", """
from rest_framework.views import APIView
from rest_framework.response import Response

class AudienceView(APIView):
    def get(self, request):
        return Response({'presets': []})

    def post(self, request):
        return Response(creer(request))
""")
        backend = contract.BackendRoutes(self.base)
        backend.build()
        reader = shapes.ShapeReader(backend)
        route = ("api", "django", "ao", "audiences")
        self.assertEqual(reader.shape_of_route(route, "get"), {"presets": shapes.LISTE})
        self.assertIsNone(reader.shape_of_route(route, "post"))


class JsObjectTests(unittest.TestCase):
    def _shape(self, source):
        code, _, masked = contract.scan_js(source)
        return shapes.js_object_shape(code, masked, source.index("{"))

    def test_natures_de_base(self):
        self.assertEqual(
            self._shape("{ a: 7, b: 'x', c: [1], d: {}, e: true }"),
            {"a": shapes.NOMBRE, "b": shapes.TEXTE, "c": shapes.LISTE,
             "d": shapes.OBJET, "e": shapes.BOOLEEN})

    def test_objets_imbriques_ne_fuient_pas(self):
        forme = self._shape("{ a: { b: 1, c: 2 }, d: 3 }")
        self.assertEqual(sorted(forme), ["a", "d"])


class MockBindingTests(unittest.TestCase):
    """Le mock est relie au module que le test declare mocker, jamais au nom seul."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        write(self.base / "api" / "importApi.js", "export default {}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_module_mocke_resolu(self):
        test = write(self.base / "pages" / "Ecran.test.jsx", """
vi.mock('../api/importApi', () => ({ default: { dryRun } }))
const PAYLOAD = { apercu: [], total_lignes: 1 }
dryRun.mockResolvedValueOnce({ data: PAYLOAD })
""")
        found = shapes.mocked_payloads(test)
        self.assertEqual(len(found), 1)
        _, modules, name, forme = found[0]
        self.assertEqual(name, "dryRun")
        self.assertEqual({p.name for p in modules}, {"importApi.js"})
        self.assertEqual(forme, {"apercu": shapes.LISTE, "total_lignes": shapes.NOMBRE})

    def test_sans_vi_mock_aucun_controle(self):
        # Sans module declare, on ne devine pas : zero constat (c'est le
        # garde-fou qui a supprime 18 faux positifs sur 26).
        test = write(self.base / "pages" / "Autre.test.jsx",
                     "dryRun.mockResolvedValue({ data: { apercu: [] } })\n")
        self.assertEqual(shapes.mocked_payloads(test), [])


class DepotReelTests(unittest.TestCase):
    def test_contrat_versionne_present(self):
        contenu = shapes.CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("GENERE", contenu)
        self.assertIn("tableauMarches", contenu)

    def test_l_entete_explique_pourquoi_pas_l_openapi(self):
        entete = Path(shapes.__file__).read_text(encoding="utf-8")[:5000]
        self.assertIn("03/08/2026", entete)
        self.assertIn("OpenApiResponse(response=dict)", entete)

    def test_la_base_ne_peut_que_retrecir(self):
        self.assertIn("NE PEUT QUE RETRECIR",
                      shapes.BASELINE_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
