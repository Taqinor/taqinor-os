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


_CONTRAT_REEL = None


def contrat_reel():
    """Le contrat derive du VRAI depot, construit UNE SEULE FOIS.

    `build_contract()` relit tout le backend (~40 s) : le rappeler dans chaque
    test qui en a besoin triplait la duree du fichier.
    """
    global _CONTRAT_REEL
    if _CONTRAT_REEL is None:
        _CONTRAT_REEL = shapes.build_contract()
    return _CONTRAT_REEL


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


class EcranVersChampTests(unittest.TestCase):
    """PACT9 — attraper l'ecran qui lit un champ fantome SANS avoir de test.

    Le contrat AO est celui REELLEMENT publie par le depot (voir
    `docs/api-contracts.md`) : six cles, `echeances_dues` en NOMBRE,
    `marches_en_execution` en OBJET. Les ecrans ci-dessous sont des
    reconstitutions fideles de ce qui etait en production le 03/08/2026.
    """

    CONTRAT_AO = {
        "en_cours": shapes.OBJET,
        "echeances_dues": shapes.NOMBRE,
        "reussite": shapes.OBJET,
        "capacite": shapes.OBJET,
        "cautions": shapes.OBJET,
        "marches_en_execution": shapes.OBJET,
    }

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.client = write(self.base / "src" / "api" / "aoApi.js",
                            "export default { tableauMarches: () => "
                            "api.get('/ao/tableau-marches/') }\n")
        self.contrat = {(self.client.resolve(), "tableauMarches"):
                        ("/api/django/ao/tableau-marches", dict(self.CONTRAT_AO))}
        self._root, self._src = shapes.ROOT, shapes.FRONT_SRC
        shapes.ROOT = self.base
        shapes.FRONT_SRC = self.base / "src"

    def tearDown(self):
        shapes.ROOT, shapes.FRONT_SRC = self._root, self._src
        self.tmp.cleanup()

    def _constats(self, source: str, nom="DashboardPage.jsx"):
        write(self.base / "src" / "features" / "ao" / nom, source)
        return shapes.champs_fantomes(self.contrat)

    ECRAN_CASSE = """
import aoApi from '../../api/aoApi'
export default function DashboardPage() {
  const { data } = useResource(() => aoApi.tableauMarches(), undefined, {
    select: (res) => res.data,
  })
  return (
    <div>
      <b>{data.ao_en_cours}</b>
      <b>{data.taux_reussite}</b>
      <b>{data.cautions_immobilisees}</b>
      <b>{data.capacite_vs_engagement}</b>
      {data.echeances_dues.map((e) => <li key={e.id}>{e.libelle}</li>)}
      <span>{data.marches_en_execution}</span>
    </div>
  )
}
"""

    def test_les_quatre_champs_fantomes_de_l_AO_sont_retrouves(self):
        champs = {c[4] for c in self._constats(self.ECRAN_CASSE)}
        self.assertLessEqual(
            {"ao_en_cours", "taux_reussite", "cautions_immobilisees",
             "capacite_vs_engagement"}, champs)

    def test_le_premier_plantage_map_sur_un_nombre_est_retrouve(self):
        motifs = {c[4]: c[5] for c in self._constats(self.ECRAN_CASSE)}
        self.assertIn("echeances_dues", motifs)
        self.assertIn("map is not a function", motifs["echeances_dues"])

    def test_le_second_plantage_objet_rendu_en_JSX_est_retrouve(self):
        motifs = {c[4]: c[5] for c in self._constats(self.ECRAN_CASSE)}
        self.assertIn("marches_en_execution", motifs)
        self.assertIn("not valid as a React child",
                      motifs["marches_en_execution"])

    def test_l_ecran_CORRIGE_ne_produit_aucun_constat(self):
        # Le meme ecran, tel qu'il est aujourd'hui : zero constat. Une garde
        # qui rougirait ici serait desactivee dans la semaine.
        correct = """
import aoApi from '../../api/aoApi'
export default function DashboardPage() {
  const { data } = useResource(() => aoApi.tableauMarches(), undefined, {
    select: (res) => res.data,
  })
  const enCours = data.en_cours ?? {}
  const reussite = data.reussite ?? {}
  const cautions = data.cautions ?? {}
  const marches = data.marches_en_execution ?? {}
  const capacite = data.capacite ?? {}
  return <b>{entier(data.echeances_dues)}{enCours.total}{reussite.gagnes}
    {cautions.nombre}{marches.total}{capacite.ecart_modules}</b>
}
"""
        self.assertEqual(self._constats(correct), [])

    # ── Les trois faux positifs que l'appariement par NOM produisait ────────
    def test_homonymie_un_champ_du_MEME_nom_sur_un_AUTRE_endpoint(self):
        # POS, paie et flotte publient tous un champ `total` : apparier par nom
        # de champ tombait sous 10 % de precision. Ici l'ecran lit `total` sur
        # un endpoint QUI NE PORTE PAS DE CONTRAT -> aucun constat, jamais.
        autre = """
import posApi from '../../api/posApi'
export default function Caisse() {
  const { data } = useResource(() => posApi.tableauCaisse(), undefined, {
    select: (res) => res.data,
  })
  return <b>{data.total}{data.echeances_dues}</b>
}
"""
        write(self.base / "src" / "api" / "posApi.js", "export default {}\n")
        self.assertEqual(self._constats(autre, nom="Caisse.jsx"), [])

    def test_un_nom_de_variable_aussi_utilise_comme_parametre_est_abandonne(self):
        # LE piege mesure : `const r = await aoApi.tableauMarches()` lie `r`,
        # mais `.then((r) => r.data.results)` ailleurs dans le MEME fichier
        # designe un AUTRE endpoint. Cinq faux positifs sur cinq (ged, audit,
        # ia, monitoring, ventes) venaient de la.
        ambigu = """
import aoApi from '../../api/aoApi'
export default function Ecran() {
  const charger = async () => {
    const r = await aoApi.tableauMarches()
    setStats(r.data.en_cours)
  }
  autreApi.getAcls().then((r) => setEntries(r.data?.results ?? []))
}
"""
        self.assertEqual(self._constats(ambigu, nom="Ecran.jsx"), [])

    def test_sans_select_data_on_n_apparie_pas(self):
        # Sans `select: (r) => r.data`, la variable porte peut-etre la reponse
        # axios entiere : accuser reviendrait a deviner.
        sans_select = """
import aoApi from '../../api/aoApi'
export default function Ecran() {
  const { data } = useResource(() => aoApi.tableauMarches())
  return <b>{data.champ_invente}</b>
}
"""
        self.assertEqual(self._constats(sans_select, nom="Ecran.jsx"), [])

    def test_une_variable_liee_deux_fois_est_abandonnee(self):
        deux_fois = """
import aoApi from '../../api/aoApi'
function A() {
  const { data } = useResource(() => aoApi.tableauMarches(), undefined, {
    select: (res) => res.data,
  })
  return <b>{data.champ_invente}</b>
}
function B() {
  const { data } = useResource(() => autreApi.autre(), undefined, {
    select: (res) => res.data,
  })
  return <b>{data.autre_champ}</b>
}
"""
        self.assertEqual(self._constats(deux_fois, nom="Deux.jsx"), [])

    def test_le_depot_reel_ne_produit_AUCUN_constat(self):
        # L'exigence de PACT9 : zero faux positif. Cette garde n'est livrable
        # qu'a cette condition — une garde bruyante sera desactivee, et la
        # recidive serait la cinquieme.
        shapes.ROOT, shapes.FRONT_SRC = self._root, self._src
        try:
            constats = shapes.champs_fantomes(contrat_reel())
        finally:
            shapes.ROOT = self.base
            shapes.FRONT_SRC = self.base / "src"
        self.assertEqual(constats, [], f"faux positifs PACT9 : {constats}")


class EchantillonDeContratTests(unittest.TestCase):
    """PACT10 — l'exemple partage derive du serveur, ou il rougit.

    Un exemple qui pourrit dans son coin serait pire que pas d'exemple du tout :
    les deux moities le liraient en croyant lire le serveur.
    """

    ROUTE = "/api/django/ao/tableau-marches"
    CONTRAT = {(Path("aoApi.js"), "tableauMarches"): (
        ROUTE, {"en_cours": shapes.OBJET, "echeances_dues": shapes.NOMBRE})}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.apps = Path(self.tmp.name) / "apps"

    def tearDown(self):
        self.tmp.cleanup()

    def _constats(self, document: str):
        write(self.apps / "ao" / "contract_samples" / "tableau_marches.json",
              document)
        return shapes.echantillons_de_contrat(self.CONTRAT, self.apps)

    def test_un_exemple_conforme_ne_produit_rien(self):
        self.assertEqual(self._constats(
            '{"endpoint": "GET /api/django/ao/tableau-marches/",'
            ' "exemple": {"en_cours": {"total": 3}, "echeances_dues": 2}}'), [])

    def test_une_cle_inventee_par_l_exemple_rougit(self):
        constats = self._constats(
            '{"endpoint": "GET /api/django/ao/tableau-marches/",'
            ' "exemple": {"en_cours": {}, "echeances_dues": 2, "ao_en_cours": 7}}')
        self.assertEqual([c[4] for c in constats], ["ao_en_cours"])

    def test_une_cle_omise_par_l_exemple_rougit(self):
        # Un exemple incomplet laisse un champ HORS contrat : la moitie qui le
        # lit croit que le champ n'existe pas.
        constats = self._constats(
            '{"endpoint": "GET /api/django/ao/tableau-marches/",'
            ' "exemple": {"en_cours": {}}}')
        self.assertEqual([c[4] for c in constats], ["echeances_dues"])

    def test_une_nature_incompatible_rougit(self):
        # LE plantage du 03/08 : `echeances_dues` est un NOMBRE cote serveur,
        # une LISTE dans la charge utile inventee par le frontend.
        constats = self._constats(
            '{"endpoint": "GET /api/django/ao/tableau-marches/",'
            ' "exemple": {"en_cours": {}, "echeances_dues": []}}')
        self.assertEqual(len(constats), 1)
        self.assertIn("en nombre", constats[0][5])
        self.assertIn("en liste", constats[0][5])

    def test_un_endpoint_hors_contrat_ne_rougit_jamais(self):
        # Un doute ne rougit JAMAIS : la forme de cet endpoint n'est pas
        # certaine statiquement, donc on n'accuse pas son exemple.
        self.assertEqual(self._constats(
            '{"endpoint": "GET /api/django/ao/inconnu/",'
            ' "exemple": {"quoi": 1}}'), [])

    def test_un_fichier_malforme_rougit_avec_le_format_attendu(self):
        constats = self._constats('{"exemple": {}}')
        self.assertEqual(len(constats), 1)
        self.assertIn("contract_samples/README.md", constats[0][5])

    def test_l_echantillon_pilote_du_depot_est_conforme(self):
        # Le module pilote de PACT10 : `apps/ao/contract_samples/`.
        fichiers = shapes.fichiers_echantillons()
        self.assertTrue(any(f.name == "tableau_marches.json" for f in fichiers),
                        "l'echantillon pilote AO a disparu")
        self.assertEqual(shapes.echantillons_de_contrat(contrat_reel()), [])


class MocksLitterauxTests(unittest.TestCase):
    """PACT13 — un mock écrit à la main est une DEUXIÈME source de vérité.

    Dès que l'endpoint porte un exemple committé (PACT10), le test l'importe.
    """

    ROUTE = "/api/django/ao/tableau-marches"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.apps = self.base / "apps"
        write(self.apps / "ao" / "contract_samples" / "tableau_marches.json",
              '{"endpoint": "GET /api/django/ao/tableau-marches/",'
              ' "exemple": {"echeances_dues": 2}}')
        self.client = write(self.base / "src" / "api" / "aoApi.js", "\n")
        self.contrat = {(self.client.resolve(), "tableauMarches"):
                        (self.ROUTE, {"echeances_dues": shapes.NOMBRE})}
        self._root, self._src = shapes.ROOT, shapes.FRONT_SRC
        shapes.ROOT, shapes.FRONT_SRC = self.base, self.base / "src"

    def tearDown(self):
        shapes.ROOT, shapes.FRONT_SRC = self._root, self._src
        self.tmp.cleanup()

    def _constats(self, source: str):
        write(self.base / "src" / "features" / "ao" / "DashboardPage.test.jsx",
              source)
        return shapes.mocks_litteraux_sous_contrat(self.contrat, self.apps)

    TEST_LITTERAL = """
vi.mock('../../api/aoApi', () => ({ default: { tableauMarches } }))
const PAYLOAD = { ao_en_cours: 7, echeances_dues: [1, 2] }
tableauMarches.mockResolvedValue({ data: PAYLOAD })
"""

    def test_une_charge_utile_ecrite_a_la_main_est_REFUSEE(self):
        constats = self._constats(self.TEST_LITTERAL)
        self.assertEqual(len(constats), 1)
        motif = constats[0][5]
        self.assertIn("ECRITE A LA MAIN", motif)

    def test_le_message_NOMME_la_fixture_a_importer(self):
        # Une garde qui refuse sans dire par quoi remplacer est une garde qu'on
        # contourne. Le message porte l'import ET l'appel exacts.
        motif = self._constats(self.TEST_LITTERAL)[0][5]
        self.assertIn(shapes.FIXTURE_CONTRAT, motif)
        self.assertIn("reponseContrat('ao', 'tableau_marches')", motif)
        self.assertIn("contract_samples/tableau_marches.json", motif)

    def test_un_test_qui_IMPORTE_la_fixture_passe(self):
        source = (
            "import { reponseContrat } from '../../test/fixtures/contractSamples'\n"
            + self.TEST_LITTERAL)
        self.assertEqual(self._constats(source), [])

    def test_un_endpoint_SANS_exemple_committe_n_est_jamais_refuse(self):
        # Portée délibérée : exiger une fixture qui n'existe pas serait
        # commander du travail impossible. La migration se fait app par app.
        contrat = {(self.client.resolve(), "autreFonction"):
                   ("/api/django/ao/autre", {"x": shapes.NOMBRE})}
        write(self.base / "src" / "features" / "ao" / "Autre.test.jsx",
              "vi.mock('../../api/aoApi', () => ({ default: { autreFonction } }))\n"
              "autreFonction.mockResolvedValue({ data: { x: 1 } })\n")
        self.assertEqual(
            shapes.mocks_litteraux_sous_contrat(contrat, self.apps), [])

    def test_le_depot_reel_ne_produit_aucun_constat(self):
        # Le module pilote AO est migré : la garde doit être verte, sinon elle
        # commande une migration qui n'a pas de fixture.
        shapes.ROOT, shapes.FRONT_SRC = self._root, self._src
        try:
            constats = shapes.mocks_litteraux_sous_contrat(contrat_reel())
        finally:
            shapes.ROOT, shapes.FRONT_SRC = self.base, self.base / "src"
        self.assertEqual(constats, [], f"tests à migrer (PACT13) : {constats}")

    def test_le_pilote_AO_importe_bien_la_fixture(self):
        pilote = (self._root / "frontend" / "src" / "features" / "ao"
                  / "DashboardPage.test.jsx")
        source = pilote.read_text(encoding="utf-8")
        self.assertIn(shapes.FIXTURE_CONTRAT, source)
        self.assertIn("exempleContrat('ao', 'tableau_marches')", source)
        # La charge utile ne doit plus être retapée dans le fichier.
        self.assertNotIn("const PAYLOAD = {", source)


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
