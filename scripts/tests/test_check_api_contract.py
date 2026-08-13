"""Tests de scripts/check_api_contract.py (garde front<->back du 03/08/2026).

Stdlib pur (unittest), aucune base de donnees, aucun Django. Lancer :
    python -m unittest scripts.tests.test_check_api_contract -v

Chaque test correspond a un piege REEL rencontre en calibrant la garde sur le
depot : la garde ne vaut que si elle attrape les vrais 404 SANS crier au loup,
et chacun des cas ci-dessous a produit, en cours de route, soit un faux
negatif, soit une avalanche de faux positifs.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_api_contract as cac  # noqa: E402


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class NormaliseRouteTests(unittest.TestCase):
    def test_convertisseur_django(self):
        self.assertEqual(cac.normalise_route("devis/<int:pk>/pdf/")[0],
                         ["devis", cac.ANY, "pdf"])

    def test_groupe_nomme_avant_convertisseur(self):
        # Regression : `<[^>]+>` mangeait `<downtime_id>` et laissait un
        # segment illisible -> toutes les @action a parametre imbrique
        # (sav, installations) devenaient de faux positifs.
        segments, opaque = cac.normalise_route(
            r"downtime/(?P<downtime_id>[^/.]+)/cloturer")
        self.assertEqual(segments, ["downtime", cac.ANY, "cloturer"])
        self.assertFalse(opaque)

    def test_path_converter_rend_opaque(self):
        _, opaque = cac.normalise_route("fichiers/<path:chemin>")
        self.assertTrue(opaque)


class TrieTests(unittest.TestCase):
    def setUp(self):
        self.trie = cac.RouteTrie()
        self.trie.add(("api", "django", "ao", "appels-offres", cac.ANY))

    def test_joker_backend(self):
        self.assertTrue(self.trie.matches(("api", "django", "ao", "appels-offres", "7")))

    def test_joker_frontend(self):
        # `/ventes/${resource}/` : un segment dynamique cote client matche
        # n'importe quel segment serveur (aucune accusation sur un doute).
        self.assertTrue(self.trie.matches(
            ("api", "django", "ao", cac.ANY, "7")))

    def test_longueur_differente(self):
        self.assertFalse(self.trie.matches(("api", "django", "ao", "appels-offres")))

    def test_prefixe_opaque(self):
        opaque = cac.RouteTrie()
        opaque.add(("api", "django", "installations", "programmes"))
        self.assertTrue(opaque.covers_prefix_of(
            ("api", "django", "installations", "programmes", "3", "budget")))
        self.assertFalse(opaque.covers_prefix_of(
            ("api", "django", "installations", "chantiers")))


class ScanJsTests(unittest.TestCase):
    def test_commentaires_retires_mais_longueur_conservee(self):
        src = "const a = 1 // /reporting/quote-to-cash\nconst b = 2\n"
        code, _, _ = cac.scan_js(src)
        self.assertEqual(len(code), len(src))
        self.assertNotIn("quote-to-cash", code)
        self.assertEqual(code.count("\n"), src.count("\n"))

    def test_bloc_de_commentaire(self):
        code, _, _ = cac.scan_js("/* api.get('/faux/chemin/') */\nvrai\n")
        self.assertNotIn("faux", code)


class ExtractionTests(unittest.TestCase):
    """Les 4 mecanismes sans lesquels la mesure naive etait fausse."""

    def _paths(self, source: str):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = write(base / "frontend" / "src" / "api" / "xApi.js", source)
            ancien = cac.ROOT
            cac.ROOT = base
            try:
                extractor = cac.FrontendCalls([target])
                extractor.collect()
            finally:
                cac.ROOT = ancien
            return [raw for _, _, raw, _ in extractor.calls]

    def test_litteral_simple(self):
        self.assertIn("/crm/leads/", self._paths("api.get('/crm/leads/')"))

    def test_commentaire_ignore(self):
        # Le faux positif mesure : une route d'ECRAN citee dans un commentaire.
        self.assertEqual(self._paths("// ecran /reporting/quote-to-cash\n"), [])

    def test_constante_de_base(self):
        source = "const P = '/gestion-projet'\napi.get(`${P}/projets/`)"
        self.assertIn("/gestion-projet/projets/", self._paths(source))

    def test_fabrique_partagee(self):
        source = ("const crud = makeResourceFactory(api, '/ao')\n"
                  "const x = { zones: crud('zones') }")
        self.assertIn("/ao/zones/", self._paths(source))

    def test_fabrique_locale(self):
        source = ("function crud(slug) {\n"
                  "  const base = `/qhse/${slug}/`\n"
                  "  return { list: () => api.get(base) }\n"
                  "}\n"
                  "const x = { capa: crud('capa') }")
        self.assertIn("/qhse/capa/", self._paths(source))

    def test_suffixe_ternaire_de_requete(self):
        # `${flag ? '?cascade=1' : ''}` n'est PAS un segment de chemin.
        source = "api.post(`/core/modules/${key}/desactiver/${c ? '?cascade=1' : ''}`)"
        resolved = self._paths(source)[0]
        self.assertEqual(cac.normalise_call(resolved, "api/django"),
                         ("api", "django", "core", "modules", cac.ANY, "desactiver"))

    def test_ternaire_hisse_dans_une_variable(self):
        # PACT5 — LE seul faux positif produit par l'elargissement du perimetre
        # a tout `frontend/src` : `pages/parametres/ExportSauvegarde.jsx` hisse
        # le ternaire de suffixe hors du gabarit. Sans mecanisme, la garde
        # accusait `/parametres/config-import/<>` sur du code CORRECT.
        source = ("const mode = overwrite ? '?mode=overwrite' : ''\n"
                  "api.post(`/parametres/config-import/${mode}`, bundle)")
        resolved = self._paths(source)[0]
        self.assertEqual(cac.normalise_call(resolved, "api/django"),
                         ("api", "django", "parametres", "config-import"))

    def test_ternaire_hisse_mixte_reste_un_segment(self):
        # Regle STRICTE : une branche qui PEUT etre un segment de chemin n'est
        # jamais repliee — sinon la garde masquerait un appel reel.
        source = ("const seg = flag ? 'archive' : ''\n"
                  "api.get(`/stock/produits/${seg}/`)")
        resolved = self._paths(source)[0]
        self.assertEqual(cac.normalise_call(resolved, "api/django"),
                         ("api", "django", "stock", "produits", cac.ANY))

    def test_ternaire_hisse_ne_saute_pas_l_instruction(self):
        # Le balayage de fin d'instruction se fait sur le code MASQUE : un `;`
        # a l'interieur d'une chaine ne doit pas couper l'expression.
        self.assertEqual(cac.ternaire_hisse("x ? '?a=1;b=2' : ''"), "")
        self.assertIsNone(cac.ternaire_hisse("x ? 'archive' : 'brouillon'"))
        self.assertIsNone(cac.ternaire_hisse("unAppel()"))

    def test_appel_ecrit_directement_dans_un_ecran(self):
        # PACT5 — la forme qui echappait a la garde : un `api.get` dans le
        # corps d'un composant, pas dans un client `*Api.js`.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ecran = write(base / "frontend" / "src" / "pages" / "stock" / "StockList.jsx",
                          "const exportXlsx = () => api.get('/stock/valorisation-xlsx/')")
            write(base / "frontend" / "src" / "features" / "x" / "X.test.jsx",
                  "api.get('/faux/chemin/')")
            ancien_root, ancien_src = cac.ROOT, cac.FRONT_SRC
            cac.ROOT, cac.FRONT_SRC = base, base / "frontend" / "src"
            try:
                fichiers = cac.frontend_files()
            finally:
                cac.ROOT, cac.FRONT_SRC = ancien_root, ancien_src
            self.assertIn(ecran, fichiers)
            self.assertTrue(all(".test." not in p.name for p in fichiers))


class BackendResolutionTests(unittest.TestCase):
    """Resolution de l'URLconf : routeur, @action, include, router.urls."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        write(self.base / "erp_agentique" / "urls.py", """
from django.urls import include, path
urlpatterns = [
    path('api/django/', include([path('ao/', include('apps.ao.urls'))])),
]
""")
        write(self.base / "apps" / "ao" / "urls.py", """
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AffaireViewSet
router = DefaultRouter()
router.register(r'appels-offres', AffaireViewSet, basename='ao-affaire')
urlpatterns = router.urls + [path('tableau-marches/', 'vue')]
""")
        write(self.base / "apps" / "ao" / "views.py", """
from rest_framework import viewsets
from rest_framework.decorators import action

class AffaireViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def grand_livre(self, request, pk=None):
        pass

    @action(detail=False, url_path='a-relancer')
    def a_relancer(self, request):
        pass
""")

    def tearDown(self):
        self.tmp.cleanup()

    def _routes(self):
        backend = cac.BackendRoutes(self.base)
        backend.build()
        return backend

    def test_liste_et_detail(self):
        routes = self._routes().routes
        self.assertIn(("api", "django", "ao", "appels-offres"), routes)
        # PACT151 — la route de detail est marquee `<pk>`, pas `<>` : elle est
        # ajoutee inconditionnellement par le routeur, donc elle ne peut pas
        # etre un joker symetrique.
        self.assertIn(("api", "django", "ao", "appels-offres", cac.PK), routes)

    def test_router_urls_dans_urlpatterns(self):
        # `urlpatterns = router.urls + [...]` : sans ce cas, TOUTES les
        # ressources du routeur disparaissaient (mesure : 83 faux positifs).
        self.assertIn(("api", "django", "ao", "tableau-marches"), self._routes().routes)
        self.assertIn(("api", "django", "ao", "appels-offres"), self._routes().routes)

    def test_url_path_par_defaut_est_le_nom_de_methode(self):
        # LE piege de l'onglet Grand-livre : DRF garde le souligne.
        routes = self._routes().routes
        self.assertIn(("api", "django", "ao", "appels-offres", cac.ANY, "grand_livre"), routes)
        self.assertNotIn(("api", "django", "ao", "appels-offres", cac.ANY, "grand-livre"), routes)

    def test_url_path_explicite(self):
        self.assertIn(("api", "django", "ao", "appels-offres", "a-relancer"),
                      self._routes().routes)

    def test_viewset_introuvable_rend_opaque(self):
        write(self.base / "apps" / "ao" / "views.py", "")
        backend = self._routes()
        self.assertIn(("api", "django", "ao", "appels-offres"), backend.opaque)


class JokerPkTests(unittest.TestCase):
    """PACT151 — le `<pk>` d'un routeur n'avale plus un nom d'action manque.

    LES QUATRE CAS HISTORIQUES, MESURES. `_expand_router` ajoute
    `base + (<pk>,)` pour CHAQUE `router.register`, meme quand le ViewSet n'a
    ni `retrieve` ni `list` ; `compatible()` traitait ce joker symetriquement,
    donc un dernier segment litteral en kebab-case y matchait TOUJOURS. Quatre
    appels reels du depot etaient ainsi avales — la garde restait VERTE sur
    quatre 404 :

        /ventes/devis/action-requise/   (PACT17)
        /compta/ecritures/grand-livre/  (PACT18)
        /rh/heures-supp/export-paie/    (PACT19)
        /rh/demandes-conge/calendrier-equipe/ (PACT19)

    Chacun est reproduit ci-dessous SANS son correctif (l'@action n'existe pas)
    : le test est rouge avant PACT151 (la garde matchait), vert apres.
    """

    CAS = (
        (("api", "django", "ventes", "devis"), "action-requise"),
        (("api", "django", "compta", "ecritures"), "grand-livre"),
        (("api", "django", "rh", "heures-supp"), "export-paie"),
        (("api", "django", "rh", "demandes-conge"), "calendrier-equipe"),
    )

    def _trie(self, base, action=None):
        """Inventaire REEL d'un `router.register` nu, par le vrai resolveur.

        On passe deliberement par `BackendRoutes` et non par un `trie.add`
        ecrit a la main : c'est `_expand_router` qui ajoute inconditionnellement
        la route de detail, et c'est donc lui que ce test doit exercer. Un test
        qui poserait `<pk>` lui-meme serait vert AVANT le correctif.
        """
        app, prefixe = base[2], base[3]
        extra = ""
        if action:
            extra = ("\n    @action(detail=False, url_path=%r)\n"
                     "    def sous_route(self, request):\n        pass\n" % action)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        racine = Path(tmp.name)
        write(racine / "erp_agentique" / "urls.py",
              "from django.urls import include, path\n"
              "urlpatterns = [path('api/django/', include([\n"
              "    path('%s/', include('apps.%s.urls')),\n"
              "]))]\n" % (app, app))
        write(racine / "apps" / app / "urls.py",
              "from django.urls import include, path\n"
              "from rest_framework.routers import DefaultRouter\n"
              "from .views import CibleViewSet\n"
              "router = DefaultRouter()\n"
              "router.register(r'%s', CibleViewSet, basename='cible')\n"
              "urlpatterns = [path('', include(router.urls))]\n" % prefixe)
        write(racine / "apps" / app / "views.py",
              "from rest_framework import viewsets\n"
              "from rest_framework.decorators import action\n\n"
              "class CibleViewSet(viewsets.ModelViewSet):\n"
              "    pass\n" + extra)
        backend = cac.BackendRoutes(racine)
        backend.build()
        trie = cac.RouteTrie()
        for route in backend.routes:
            trie.add(route)
        return trie

    def test_les_quatre_404_historiques_ne_sont_plus_avales(self):
        for base, action in self.CAS:
            with self.subTest(action=action):
                self.assertFalse(
                    self._trie(base).matches(base + (action,)),
                    f"/{'/'.join(base)}/{action}/ doit etre un 404 visible")

    def test_l_action_reellement_enregistree_matche(self):
        # Le correctif backend (l'@action existe) doit rendre la garde verte :
        # sans cela, PACT151 casserait les appels CORRECTS.
        for base, action in self.CAS:
            with self.subTest(action=action):
                self.assertTrue(self._trie(base, action=action).matches(base + (action,)))

    def test_une_vraie_cle_primaire_matche_toujours(self):
        base = ("api", "django", "ventes", "devis")
        trie = self._trie(base)
        for cle in ("7", "42", "a3f1b2c4-1111-2222-3333-444455556666", "AB12"):
            with self.subTest(cle=cle):
                self.assertTrue(trie.matches(base + (cle,)))

    def test_un_segment_dynamique_du_frontend_matche_toujours(self):
        # Principe anti-faux-positif : `${id}` cote client est un joker.
        base = ("api", "django", "ventes", "devis")
        self.assertTrue(self._trie(base).matches(base + (cac.ANY,)))

    def test_un_parametre_d_url_declare_reste_un_joker(self):
        # `path('<str:token>/')` produit un `ANY`, pas un `<pk>` de routeur :
        # un jeton en kebab-case doit continuer d'y matcher.
        trie = cac.RouteTrie()
        trie.add(("api", "django", "ged", "public", cac.ANY))
        self.assertTrue(trie.matches(("api", "django", "ged", "public", "mon-jeton")))

    def test_seul_le_DERNIER_segment_est_concerne(self):
        # `/devis/<pk>/lignes/` : le segment kebab-case n'est pas terminal, la
        # route de detail est reellement traversee.
        base = ("api", "django", "ventes", "devis")
        trie = cac.RouteTrie()
        trie.add(base + (cac.ANY, "lignes"))
        self.assertTrue(trie.matches(base + ("mon-devis", "lignes")))

    def test_est_nom_d_action(self):
        for segment in ("action-requise", "grand-livre", "export-paie",
                        "calendrier-equipe"):
            self.assertTrue(cac.est_nom_d_action(segment), segment)
        for segment in ("7", "42", "abc", "Grand-Livre", "a3f1-b2c4", "x_y"):
            self.assertFalse(cac.est_nom_d_action(segment), segment)

    def test_compatible_est_symetrique_avec_le_trie(self):
        base = ("api", "django", "ventes", "devis")
        self.assertFalse(cac.compatible(base + ("action-requise",), base + (cac.PK,)))
        self.assertTrue(cac.compatible(base + ("7",), base + (cac.PK,)))
        self.assertTrue(cac.compatible(base + (cac.ANY,), base + (cac.PK,)))

    def test_la_route_de_detail_reste_bien_declaree(self):
        # Garde-fou : le correctif ne doit pas SUPPRIMER la route de detail
        # (ce serait une avalanche de faux positifs sur tous les `/x/${id}/`).
        base = ("api", "django", "ventes", "devis")
        backend_routes = self._trie(base).root
        noeud = backend_routes
        for segment in base:
            noeud = noeud[segment]
        self.assertIn(cac.PK, noeud)


class BaselineTests(unittest.TestCase):
    def test_la_base_ne_peut_que_retrecir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.txt"
            cac.write_baseline({"/api/django/ao/zones"}, path)
            self.assertEqual(cac.load_baseline(path), {"/api/django/ao/zones"})
            entetes = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                       if ln.startswith("#")]
            self.assertTrue(any("RETRECIR" in ln for ln in entetes))

    def test_signature_sans_fichier_ni_ligne(self):
        # Lecon du depot : une allowlist `fichier:ligne` derive au moindre
        # decalage de ligne. La signature est le CHEMIN, rien d'autre.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.txt"
            cac.write_baseline({"/api/django/ao/zones"}, path)
            self.assertNotIn(":", path.read_text(encoding="utf-8").split("zones")[1])


class DepotReelTests(unittest.TestCase):
    """Garde-fous sur le vrai depot (rapides : lecture de fichiers seule)."""

    def test_la_base_de_reference_existe_et_est_documentee(self):
        contenu = cac.BASELINE_PATH.read_text(encoding="utf-8")
        self.assertIn("NE PEUT QUE RETRECIR", contenu)

    def test_l_entete_explique_l_incident(self):
        entete = Path(cac.__file__).read_text(encoding="utf-8")[:4000]
        self.assertIn("03/08/2026", entete)
        self.assertIn("bibliotheque", entete.lower())


if __name__ == "__main__":
    unittest.main()
