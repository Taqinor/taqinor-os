"""Tests de scripts/check_ecrans_atteignables.py (garde d'atteignabilite du 03/08/2026).

Stdlib pur (unittest), aucune base de donnees, aucun node, aucun build. Lancer :
    python -m unittest scripts.tests.test_check_ecrans_atteignables -v

Chaque test correspond a un piege REEL rencontre en calibrant la garde sur le
depot. Une garde d'atteignabilite ne vaut RIEN si elle crie au loup : un
sous-composant (ligne de tableau, badge, tiroir) est atteint PAR SON PARENT, un
`routes: []` deliberement vide est une lecture VALIDE, et un placeholder pose
devant une fonctionnalite qui n'existe pas encore est LEGITIME. Les tests
ci-dessous verrouillent ces trois silences autant que les detections.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_ecrans_atteignables as cea  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FauxDepot:
    """Arborescence frontend jetable, branchee sur les constantes du module."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "frontend" / "src"
        self.features = self.src / "features"
        self.features.mkdir(parents=True)
        self.pages = self.src / "pages"
        self.pages.mkdir(parents=True)
        write(self.src / "main.jsx", "import router from './router'\n")
        self._sauvegarde = (
            cea.FRONT_SRC, cea.FEATURES, cea.PAGES, cea.ENTRY, cea.ROOT)
        cea.FRONT_SRC = self.src
        cea.FEATURES = self.features
        cea.PAGES = self.pages
        cea.ENTRY = self.src / "main.jsx"
        cea.ROOT = Path(self.tmp.name)
        cea._CACHE.clear()

    def fichier(self, relatif: str, contenu: str) -> Path:
        return write(self.src / relatif, contenu)

    def close(self):
        cea.FRONT_SRC, cea.FEATURES, cea.PAGES, cea.ENTRY, cea.ROOT = self._sauvegarde
        cea._CACHE.clear()
        self.tmp.cleanup()


class BaseDepot(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)

    def orphelins(self):
        constats, _ = cea.analyse()
        return sorted(c[1] for c in constats if c[0] == "inatteignable")

    def bouchons(self):
        constats, _ = cea.analyse()
        return sorted((c[0], c[1]) for c in constats
                      if c[0] not in ("inatteignable", "sans-nav"))

    def sans_nav(self):
        constats, _ = cea.analyse()
        return sorted(c[1] for c in constats if c[0] == "sans-nav")


# ===========================================================================
# Resolution de modules
# ===========================================================================

class ResolutionTests(BaseDepot):
    def test_extension_implicite_et_index(self):
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/x/panneau/index.jsx", "export default 1\n")
        importateur = self.depot.src / "features" / "x" / "module.config.jsx"
        self.assertEqual(cea.resoudre("./Ecran", importateur).name, "Ecran.jsx")
        self.assertEqual(cea.resoudre("./Ecran.jsx", importateur).name, "Ecran.jsx")
        self.assertEqual(cea.resoudre("./panneau", importateur).name, "index.jsx")

    def test_paquet_npm_et_feuille_de_style_ignores(self):
        """`import './index.css'` et `from 'react'` ne sont pas des ecrans."""
        self.depot.fichier("features/x/index.css", "body{}")
        importateur = self.depot.src / "features" / "x" / "a.jsx"
        self.assertIsNone(cea.resoudre("react", importateur))
        self.assertIsNone(cea.resoudre("./index.css", importateur))

    def test_toutes_les_formes_d_import_sont_lues(self):
        code = (
            "import A from './A'\n"
            "export { default as B } from './B'\n"
            "const C = lazy(() => import('./C'))\n"
            "import './style.css'\n"
        )
        self.assertEqual(
            sorted(cea.specificateurs(code)),
            ["./A", "./B", "./C", "./style.css"])


# ===========================================================================
# Atteignabilite — le coeur anti-faux-positif
# ===========================================================================

class AtteignabiliteTests(BaseDepot):
    def _config(self, app: str, corps: str):
        return self.depot.fichier(f"features/{app}/module.config.jsx", corps)

    def test_sous_composant_credite_par_son_parent(self):
        """Un tiroir/une ligne de tableau n'est JAMAIS route : son parent l'est.

        C'est le faux positif qui aurait rendu la garde inutilisable : sur le
        depot reel, la majorite des `.jsx` d'une app sont des sous-composants.
        """
        self._config("x", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const config = { key:'x', routes: [{ path:'/x', component: Ecran }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Ligne from './table/Ligne'\nexport default 1\n")
        self.depot.fichier("features/x/table/Ligne.jsx",
                           "import Badge from './Badge'\nexport default 1\n")
        self.depot.fichier("features/x/table/Badge.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(), [])

    def test_ecran_non_route_est_signale(self):
        self._config("x", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const config = { key:'x', routes: [{ path:'/x', component: Ecran }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/x/Orphelin.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(),
                         ["frontend/src/features/x/Orphelin.jsx"])

    def test_un_test_n_est_pas_un_chemin_d_acces(self):
        """Un ecran importe SEULEMENT par son test reste inatteignable.

        Cas reel : magasin/scan/*, credit/*, messaging/VoiceRecorder — tous
        verts en tests unitaires, tous invisibles dans l'app.
        """
        self._config("x", "const config = { key:'x', routes: [] }\nexport default config\n")
        self.depot.fichier("features/x/Orphelin.jsx", "export default 1\n")
        self.depot.fichier("features/x/Orphelin.test.jsx",
                           "import O from './Orphelin'\n")
        self.assertEqual(self.orphelins(),
                         ["frontend/src/features/x/Orphelin.jsx"])

    def test_ecran_monte_depuis_le_routeur_principal(self):
        """Tout ce que `main.jsx` atteint compte (routes hors module.config).

        `router/index.jsx` monte directement des ecrans de features (portail,
        contrats, rh/Kiosque) : les ignorer aurait produit ~9 faux positifs.
        """
        self._config("x", "const config = { key:'x', routes: [] }\nexport default config\n")
        self.depot.fichier("router/index.jsx",
                           "const P = lazy(() => import('../features/x/Portail'))\n")
        self.depot.fichier("features/x/Portail.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(), [])

    def test_routes_vides_ne_rendent_pas_la_config_opaque(self):
        """`routes: []` (module route ailleurs) est une lecture VALIDE."""
        self._config("x", "const config = { key:'x', routes: [] }\nexport default config\n")
        self.depot.fichier("features/x/Orphelin.jsx", "export default 1\n")
        config = cea.ConfigModule(self.depot.features / "x" / "module.config.jsx")
        self.assertFalse(config.opaque)
        self.assertEqual(self.orphelins(),
                         ["frontend/src/features/x/Orphelin.jsx"])

    def test_config_illisible_est_opaque_et_muette(self):
        """Forme inattendue -> on credite TOUT et on n'accuse RIEN."""
        self._config("x", (
            "import Ecran from './Ecran'\n"
            "const config = { key:'x', routes: baseRoutes.concat(extra) }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        config = cea.ConfigModule(self.depot.features / "x" / "module.config.jsx")
        self.assertTrue(config.opaque)
        self.assertEqual(self.orphelins(), [])


# ===========================================================================
# credits_hors_routes — extension PACT173 (07/08/2026)
# ===========================================================================

class CreditsHorsRoutesTests(BaseDepot):
    """``atteignables()`` ajoutait ``config.path`` (le ``module.config.jsx``
    lui-meme) aux racines de la BFS : des qu'il etait depile, TOUS ses
    imports bruts etaient credites — y compris un ``lazy()`` jamais place
    dans ``routes:``. Ces tests verrouillent le trou ferme (le composant
    orphelin doit desormais sortir) SANS casser les deux cas reels mesures
    (wrapper local, prop JSX) ni le cas opaque (credit total inchange)."""

    def test_lazy_jamais_route_est_desormais_signale(self):
        """LE controle negatif exige par PACT150/PACT173 : un `lazy()`
        ajoute sans jamais etre place dans `routes:`, ni rendu comme JSX, ni
        passe en prop, doit desormais sortir en inatteignable — AVANT ce
        correctif, il etait credite par son seul VOISINAGE dans le fichier
        (`imports_de(config.path)` credit tout, sans regarder l'usage)."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const Fantome = lazy(() => import('./Fantome'))\n"
            "const config = { key:'x', routes: "
            "[{ path:'/x', component: Ecran }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/x/Fantome.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(),
                         ["frontend/src/features/x/Fantome.jsx"])

    def test_lazy_rendu_par_un_wrapper_local_est_credite(self):
        """Cas reel mesure : `adsengine/module.config.jsx` — un wrapper
        (`AdsCockpitScreenPrintable`) DECLARE dans le fichier et utilise
        comme `component:` rend `<AdsCockpitScreen/>`, un AUTRE composant
        `lazy()` jamais cite dans `routes:` directement."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "function EcranImprimable() {\n"
            "  return <PrintWrapper><Ecran /></PrintWrapper>\n"
            "}\n"
            "const config = { key:'x', routes: "
            "[{ path:'/x', component: EcranImprimable }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(), [])
        self.assertEqual(self.bouchons(), [])

    def test_lazy_passe_en_prop_jsx_est_credite(self):
        """Cas reel mesure : `router/index.jsx` — `PortalClientLayout` (un
        `lazy()`) n'est jamais rendu comme balise JSX, seulement passe en
        prop `shell={PortalClientLayout}`."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Layout = lazy(() => import('./Layout'))\n"
            "function Ecran() {\n"
            "  return <WithShell shell={Layout}><Contenu /></WithShell>\n"
            "}\n"
            "const config = { key:'x', routes: "
            "[{ path:'/x', component: Ecran }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Layout.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(), [])

    def test_lazy_non_route_et_non_rendu_reste_signale_meme_avec_wrapper(self):
        """Un wrapper local qui rend UN SEUL composant ne credite QUE
        celui-la — un troisieme `lazy()` sans lien nulle part reste rouge."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const Fantome = lazy(() => import('./Fantome'))\n"
            "function EcranImprimable() {\n"
            "  return <PrintWrapper><Ecran /></PrintWrapper>\n"
            "}\n"
            "const config = { key:'x', routes: "
            "[{ path:'/x', component: EcranImprimable }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/x/Fantome.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(),
                         ["frontend/src/features/x/Fantome.jsx"])

    def test_config_opaque_credite_toujours_tout_avec_ou_sans_wrapper(self):
        """Non-regression du cas opaque (piege reel rencontre en ecrivant ce
        correctif : pre-marquer `module.config.jsx` comme « vu » AVANT la BFS
        empechait par erreur la propagation de ses imports bruts pour une
        config opaque — casserait le principe anti-faux-positif existant)."""
        self.depot.fichier("features/x/module.config.jsx", (
            "import Ecran from './Ecran'\n"
            "const config = { key:'x', routes: baseRoutes.concat(extra) }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        config = cea.ConfigModule(self.depot.features / "x" / "module.config.jsx")
        self.assertTrue(config.opaque)
        self.assertEqual(self.orphelins(), [])


# ===========================================================================
# pages/** — extension PACT149 (07/08/2026)
# ===========================================================================

class PagesTests(BaseDepot):
    """`pages/**` est desormais inventorie au meme titre que `features/**`.

    Avant PACT149, `ecrans_de_features()` n'inventoriait QUE `features/` :
    un ecran mort sous `pages/` etait invisible pour toujours, meme s'il
    apparaissait dans le graphe d'atteignabilite (qui, lui, suit deja
    `pages/**` depuis `main.jsx` -> `router/index.jsx`). Cas reel trouve et
    corrige le meme jour : `pages/credit/ExpositionCreditPage.jsx`, jumeau
    perime du vivant `features/credit/ExpositionCreditPage.jsx`, supprime.
    """

    def test_ecran_pages_non_route_est_signale(self):
        """Controle negatif : le trou structurel que PACT149 ferme."""
        self.depot.fichier("router/index.jsx",
                           "const Vivant = lazy(() => import('../pages/Vivant'))\n")
        self.depot.fichier("pages/Vivant.jsx", "export default 1\n")
        self.depot.fichier("pages/Orphelin.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(),
                         ["frontend/src/pages/Orphelin.jsx"])

    def test_ecran_pages_route_est_atteignable(self):
        self.depot.fichier("router/index.jsx",
                           "const Vivant = lazy(() => import('../pages/Vivant'))\n")
        self.depot.fichier("pages/Vivant.jsx", "export default 1\n")
        self.assertEqual(self.orphelins(), [])

    def test_extension_tsx_est_inventoriee(self):
        """`.tsx` est resolu et inventorie, meme si le depot n'en a pas encore."""
        self.depot.fichier("router/index.jsx",
                           "const Vivant = lazy(() => import('../pages/Vivant'))\n")
        self.depot.fichier("pages/Vivant.tsx", "export default 1\n")
        self.depot.fichier("pages/Orphelin.tsx", "export default 1\n")
        self.assertEqual(self.orphelins(),
                         ["frontend/src/pages/Orphelin.tsx"])

    def test_app_de_distingue_features_et_pages(self):
        """`pages/credit` et `features/credit` ne sont jamais le meme bac."""
        cible_features = cea.FEATURES / "credit" / "X.jsx"
        cible_pages = cea.PAGES / "credit" / "X.jsx"
        self.assertEqual(cea.app_de(cible_features), "credit")
        self.assertEqual(cea.app_de(cible_pages), "pages/credit")


# ===========================================================================
# Route != menu — extension PACT150 (07/08/2026)
# ===========================================================================

class NavigationTests(BaseDepot):
    """Une route dans ``routes:`` menant a un vrai ecran satisfait deja le
    graphe d'imports (classe 1 muette) meme si AUCUNE entree de menu n'y mene
    jamais — cas vivant : ``/parametres/achats`` (182 lignes, WIR26) routee
    mais sans ``nav.items`` ni ``Link``/``navigate``. Ces tests verrouillent
    le detecteur ``routes_sans_nav`` : la route litterale doit avoir soit un
    ``nav.items[].to`` (n'importe quel module.config.jsx), soit un lien
    entrant reel dans un fichier LUI-MEME atteignable (jamais un test, jamais
    un fichier mort), soit un marqueur ``// contextuelle: <raison>``.
    """

    def _config_routee(self, app: str, chemin: str, extra_nav: str = "") -> Path:
        return self.depot.fichier(f"features/{app}/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            f"const config = {{ key:'{app}', nav: {{ label:'{app}', items: ["
            f"{extra_nav}] }}, routes: [{{ path:'{chemin}', component: Ecran }}] }}\n"
            "export default config\n"))

    def test_route_sans_nav_est_signalee(self):
        """Controle negatif : le trou structurel que PACT150 ferme.

        La route est bien ECRITE dans ce module.config.jsx (``path:
        '/x/rapport'``) — la garde ne doit PAS s'auto-verifier en trouvant sa
        propre declaration : seul un mot-cle de navigation EXPLICITE
        (``to``/``href``) compte dans un module.config.jsx.
        """
        self._config_routee("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.assertEqual(
            self.sans_nav(),
            ["frontend/src/features/x/module.config.jsx::/x/rapport"])

    def test_route_avec_nav_item_est_ok(self):
        self._config_routee(
            "x", "/x/rapport",
            "{ to: '/x/rapport', label: 'Rapport' }")
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.assertEqual(self.sans_nav(), [])

    def test_nav_item_d_un_AUTRE_module_config_compte(self):
        """Cas reel : ``/journal`` est routee dans `parametres`, sa nav vit
        dans `reporting` (``features/reporting/module.config.jsx``)."""
        self._config_routee("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/y/module.config.jsx", (
            "const config = { key:'y', nav: { label:'y', items: ["
            "{ to: '/x/rapport', label: 'Rapport (depuis Y)' }"
            "] }, routes: [] }\nexport default config\n"))
        self.assertEqual(self.sans_nav(), [])

    def test_lien_reel_dans_un_autre_fichier_atteignable_est_ok(self):
        """``<Link to="...">`` ecrit ailleurs (pas nav.items) suffit."""
        self._config_routee("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Barre from './Barre'\nexport default 1\n")
        self.depot.fichier("features/x/Barre.jsx",
                           "export default () => <Link to=\"/x/rapport\">R</Link>\n")
        self.assertEqual(self.sans_nav(), [])

    def test_href_compte_comme_lien(self):
        self._config_routee("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Barre from './Barre'\nexport default 1\n")
        self.depot.fichier("features/x/Barre.jsx",
                           "export default () => <a href=\"/x/rapport\">R</a>\n")
        self.assertEqual(self.sans_nav(), [])

    def test_table_de_routage_par_donnee_est_reconnue(self):
        """Cas reel mesure : `mobileHome.js` — `Directeur: '/mobile/cockpit'`
        dans un objet de donnees, jamais un appel `navigate()` litteral ni un
        `to=`/`href=`. Hors d'un module.config.jsx, tout litteral en forme de
        chemin compte (aucun risque d'auto-verification : ce fichier ne
        declare pas de route)."""
        self._config_routee("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import { TABLE } from './routage'\nexport default 1\n")
        self.depot.fichier("features/x/routage.jsx",
                           "export const TABLE = { Directeur: '/x/rapport' }\n")
        self.assertEqual(self.sans_nav(), [])

    def test_alias_de_navigate_est_reconnu(self):
        """Cas reel mesure : `NotificationBell.jsx:451` — `const goto = (p)
        => { navigate(p) }` puis `goto('/x/rapport')` : un nom de variable
        different du mot `navigate` ne doit pas produire un faux negatif."""
        self._config_routee("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Cloche from './Cloche'\nexport default 1\n")
        self.depot.fichier("features/x/Cloche.jsx", (
            "const goto = (p) => { navigate(p) }\n"
            "export default () => <button onClick={() => "
            "goto('/x/rapport')}>Aller</button>\n"))
        self.assertEqual(self.sans_nav(), [])

    def test_lien_dans_un_fichier_mort_ne_compte_pas(self):
        """Un `<Link>` ecrit dans un composant MORT (jamais importe) ne rend
        rien reel — meme defaut que celui que cette tache ferme si on le
        laissait compter : seuls les fichiers de `vus` sont scannes."""
        self._config_routee("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/x/Mort.jsx",
                           "export default () => <Link to=\"/x/rapport\">R</Link>\n")
        self.assertEqual(
            self.sans_nav(),
            ["frontend/src/features/x/module.config.jsx::/x/rapport"])

    def test_lien_dans_un_test_ne_compte_pas(self):
        """Le piege mesure par l'audit : un grep naif compte un fichier de
        test comme lien. `Barre.jsx` est atteignable (importe par Ecran), son
        test l'est « aussi » au sens du glob mais JAMAIS un point d'entree."""
        self._config_routee("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Barre from './Barre'\nexport default 1\n")
        self.depot.fichier("features/x/Barre.jsx", "export default 1\n")
        self.depot.fichier("features/x/Barre.test.jsx",
                           "export default () => <Link to=\"/x/rapport\">R</Link>\n")
        self.assertEqual(
            self.sans_nav(),
            ["frontend/src/features/x/module.config.jsx::/x/rapport"])

    def test_route_dynamique_exemptee(self):
        """Un segment `:id` est exempte — la garde ne sait pas resoudre un
        lien concret vers une instance particuliere."""
        self._config_routee("x", "/x/rapport/:id")
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.assertEqual(self.sans_nav(), [])

    def test_marqueur_contextuel_justifie(self):
        """Route volontairement hors menu, marquee explicitement."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const config = { key:'x', nav: { label:'x', items: [] }, "
            "routes: [\n"
            "  { path:'/x/rapport', component: Ecran }, "
            "// contextuelle: lien envoye par email, jamais statique\n"
            "] }\nexport default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.assertEqual(self.sans_nav(), [])

    def test_marqueur_sur_une_AUTRE_route_ne_justifie_pas_celle_ci(self):
        """Le marqueur est positionnel : il ne justifie QUE la route a
        proximite, jamais tout le fichier."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const Autre = lazy(() => import('./Autre'))\n"
            "const config = { key:'x', nav: { label:'x', items: [] }, "
            "routes: [\n"
            "  { path:'/x/rapport', component: Ecran },\n"
            "\n\n\n\n\n"
            "  { path:'/x/autre', component: Autre }, "
            "// contextuelle: lien envoye par email\n"
            "] }\nexport default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/x/Autre.jsx", "export default 1\n")
        self.assertEqual(
            self.sans_nav(),
            ["frontend/src/features/x/module.config.jsx::/x/rapport"])


# ===========================================================================
# Sujets (appariement placeholder <-> ecran reel)
# ===========================================================================

class SujetsTests(unittest.TestCase):
    def test_accents_pluriel_et_mots_vides(self):
        self.assertEqual(cea.mots_sujet("Calepinages"), {"calepinage"})
        self.assertEqual(cea.mots_sujet("Toitures & relevés"), {"toiture", "releve"})
        self.assertEqual(cea.mots_sujet("Questions terrain"), {"question", "terrain"})
        # « Tableau de bord » : que des mots vides -> aucun sujet.
        self.assertEqual(cea.mots_sujet("Tableau de bord"), set())
        # Jetons trop courts : jamais retenus (risque d'appariement fortuit).
        self.assertEqual(cea.mots_sujet("CPS QR"), set())


class PlaceholderTests(BaseDepot):
    def _app_avec_bouchon(self, avec_ecran_reel: bool):
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "function Squelette({ titre }) { return <EmptyState title={titre} /> }\n"
            "const squelette = (t) => lazy(() => Promise.resolve({ default: () => "
            "<Squelette titre={t} /> }))\n"
            "const config = { key:'x', routes: [\n"
            "  { path: '/x', component: Ecran },\n"
            "  { path: '/x/calepinages', component: squelette('Calepinages') },\n"
            "  { path: '/x/rentabilite', component: squelette('Rentabilité') },\n"
            "] }\nexport default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        if avec_ecran_reel:
            self.depot.fichier("features/x/calepinage/CalepinageStudio.jsx",
                               "export default 1\n")

    def test_bouchon_de_route_devant_un_ecran_reel(self):
        self._app_avec_bouchon(avec_ecran_reel=True)
        self.assertEqual(
            self.bouchons(),
            [("bouchon-route",
              "frontend/src/features/x/module.config.jsx::/x/calepinages")])

    def test_bouchon_sans_ecran_reel_reste_muet(self):
        """« Rentabilité » n'a pas d'ecran : le placeholder est LEGITIME."""
        self._app_avec_bouchon(avec_ecran_reel=False)
        self.assertEqual(self.bouchons(), [])

    def test_onglet_bouche_devant_un_ecran_reel(self):
        self.depot.fichier("features/x/module.config.jsx", (
            "const Fiche = lazy(() => import('./Fiche'))\n"
            "const config = { key:'x', routes: [{ path:'/x', component: Fiche }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Fiche.jsx", (
            "function TabPlaceholder({ title }) { return <EmptyState title={title} /> }\n"
            "export default function Fiche() {\n"
            "  return <Tabs items={[{ value:'d', label:'Dossier', "
            "content: <TabPlaceholder title=\"Dossier\" /> }]} />\n"
            "}\n"))
        self.depot.fichier("features/x/dossier/DossierPage.jsx", "export default 1\n")
        self.assertEqual(self.bouchons(),
                         [("bouchon-onglet",
                           "frontend/src/features/x/Fiche.jsx::dossier")])

    def test_composant_ordinaire_n_est_pas_un_bouchon(self):
        """`<Card title="Dossier" />` n'est pas un remplissage."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Fiche = lazy(() => import('./Fiche'))\n"
            "const config = { key:'x', routes: [{ path:'/x', component: Fiche }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Fiche.jsx",
                           "export default () => <Card title=\"Dossier\" />\n")
        self.depot.fichier("features/x/dossier/DossierPage.jsx", "export default 1\n")
        self.assertEqual(self.bouchons(), [])

    def test_dossier_technique_ne_prouve_aucun_ecran_cache(self):
        """`components/`, `hooks/`... ne designent pas un sujet metier."""
        self.depot.fichier("features/x/components/Truc.jsx", "export default 1\n")
        index = cea.index_sujets("x")
        self.assertNotIn("component", index)


# ===========================================================================
# Base de reference : elle ne peut que RETRECIR
# ===========================================================================

class BaseDeReferenceTests(unittest.TestCase):
    def test_ecriture_puis_relecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "allow.txt"
            cea.ecrire_base({"inatteignable|a.jsx", "bouchon-route|b.jsx::/x"}, chemin)
            self.assertEqual(cea.charger_base(chemin),
                             {"inatteignable|a.jsx", "bouchon-route|b.jsx::/x"})

    def test_signature_ne_depend_pas_du_numero_de_ligne(self):
        self.assertEqual(
            cea.signature(("inatteignable", "frontend/src/features/x/A.jsx", "x", "")),
            "inatteignable|frontend/src/features/x/A.jsx")

    def test_chemin_de_base_resolu_a_l_appel(self):
        """Piege REEL rencontre ici : `def charger_base(path=BASELINE_PATH)`
        fige le chemin a la definition du module, si bien qu'un `--write-baseline`
        lance depuis un test ecrasait la VRAIE base du depot. Le chemin DOIT
        etre resolu a l'appel."""
        sauvegarde = cea.BASELINE_PATH
        avant = sauvegarde.read_text(encoding="utf-8") if sauvegarde.is_file() else None
        self.addCleanup(lambda: setattr(cea, "BASELINE_PATH", sauvegarde))
        with tempfile.TemporaryDirectory() as tmp:
            cea.BASELINE_PATH = Path(tmp) / "allow.txt"
            cea.ecrire_base({"inatteignable|a.jsx"})
            self.assertEqual(cea.charger_base(), {"inatteignable|a.jsx"})
        apres = sauvegarde.read_text(encoding="utf-8") if sauvegarde.is_file() else None
        self.assertEqual(avant, apres, "la VRAIE base du depot a ete ecrasee")

    def test_refus_de_croissance_sans_drapeau(self):
        depot = FauxDepot()
        self.addCleanup(depot.close)
        sauvegarde = cea.BASELINE_PATH
        cea.BASELINE_PATH = Path(depot.tmp.name) / "allow.txt"
        self.addCleanup(lambda: setattr(cea, "BASELINE_PATH", sauvegarde))
        depot.fichier("features/x/module.config.jsx",
                      "const config = { key:'x', routes: [] }\nexport default config\n")
        cea.ecrire_base(set())                       # base existante et VIDE
        depot.fichier("features/x/Orphelin.jsx", "export default 1\n")
        cea._CACHE.clear()
        self.assertEqual(cea.main(["--write-baseline"]), 1)
        self.assertEqual(cea.charger_base(cea.BASELINE_PATH), set())
        cea._CACHE.clear()
        self.assertEqual(cea.main(["--write-baseline", "--autoriser-croissance"]), 0)
        self.assertEqual(cea.charger_base(cea.BASELINE_PATH),
                         {"inatteignable|frontend/src/features/x/Orphelin.jsx"})


# ===========================================================================
# Calibration sur le VRAI depot (la garde ne vaut que si elle est juste ici)
# ===========================================================================

_REEL = None


def analyse_reelle():
    global _REEL
    if _REEL is None:
        _REEL = cea.analyse()
    return _REEL


@unittest.skipUnless((ROOT / "frontend" / "src" / "features").is_dir(),
                     "frontend/src/features absent")
class DepotReelTests(unittest.TestCase):
    def test_modules_sains_ne_produisent_aucun_orphelin(self):
        """Le controle anti-faux-positif qui compte vraiment.

        Ces modules sont livres ET branches ; s'ils rougissent, la garde est
        fausse. `adsengine`/`flotte`/`gestion_projet` pesent a eux seuls ~95
        ecrans, dont une immense majorite de sous-composants.
        """
        constats, _ = analyse_reelle()
        sains = {"crm", "flotte", "gestion_projet", "contrats", "qhse", "rh",
                 "kb", "ged", "innovation", "sante", "portail", "ventes"}
        fautifs = sorted(c[1] for c in constats
                         if c[0] == "inatteignable" and c[2] in sains)
        self.assertEqual(fautifs, [])

    def test_le_passif_ao_ne_peut_que_diminuer(self):
        """Le passif AO du 03/08/2026 : 67 ecrans, 60 inatteignables.

        CE TEST A ETE REECRIT LE MEME JOUR, et le pourquoi compte : sa
        premiere version FIGEAIT ces deux nombres (``assertEqual(67)`` /
        ``assertEqual(60)``). Elle epinglait donc la MALADIE, pas la garde :
        des que la reparation a branche des ecrans, le test est devenu ROUGE
        pour cause de PROGRES. Un test qui punit la guerison est un test faux.

        L'invariant reel est un SENS DE VARIATION : le nombre d'ecrans AO
        inatteignables ne doit jamais REMONTER au-dessus du passif mesure.
        Ajouter un ecran non branche le fait croitre -> rouge legitime ; en
        brancher un le fait decroitre -> vert.
        """
        constats, _ = analyse_reelle()
        ao = [c for c in constats if c[0] == "inatteignable" and c[2] == "ao"]
        total = [p for p in cea.ecrans_de_features()
                 if p.relative_to(cea.FEATURES).parts[0] == "ao"]
        self.assertGreater(len(total), 0, "aucun ecran AO trouve : scan casse")
        self.assertLessEqual(
            len(ao), 60,
            "le nombre d'ecrans AO inatteignables a AUGMENTE depuis le passif "
            "mesure le 03/08/2026 (60) : un ecran a ete livre sans etre branche",
        )

    def test_aucun_onglet_bouche_ne_subsiste_dans_la_fiche_affaire(self):
        """Meme correction que ci-dessus : ce test AFFIRMAIT que les cinq
        onglets de la fiche affaire etaient bouches. C'etait vrai le matin du
        03/08/2026 et faux le soir — le reparer a rendu le test rouge.

        L'invariant utile est l'inverse de ce qu'il epinglait : la fiche
        affaire ne doit plus JAMAIS rendre un bouchon devant un ecran reel.
        Le pouvoir de DETECTION du detecteur, lui, est prouve par les
        controles negatifs sur module jetable (voir plus haut) — pas en
        gardant le depot malade pour avoir de quoi detecter.
        """
        constats, _ = analyse_reelle()
        onglets = sorted(c[1].split("::")[1] for c in constats
                         if c[0] == "bouchon-onglet" and "AffaireDetail" in c[1])
        self.assertEqual(
            onglets, [],
            "un onglet de la fiche affaire rend a nouveau un bouchon alors "
            "que le vrai panneau existe",
        )

    def test_les_routes_squelettes_du_menu_ao(self):
        """Dossiers cache encore un vrai ecran ; Rentabilite non — et la garde
        doit rester MUETTE sur Rentabilite. PV59 (2026-08-14) a SOLDE
        /ao/calepinages : l'EmptyState est devenu la vraie VariantesListPage,
        la route quitte donc les bouchons."""
        constats, _ = analyse_reelle()
        routes = sorted(c[1].split("::")[1] for c in constats
                        if c[0] == "bouchon-route")
        self.assertEqual(routes, ["/ao/dossiers"])

    def test_aucune_config_opaque_sur_le_depot(self):
        """Si une config devient illisible, la garde s'aveugle en silence."""
        _, stats = analyse_reelle()
        self.assertEqual(stats["opaques"], 0)
        # 45 -> 47 : le lot §E donne son PREMIER module.config.jsx a deux
        # apps qui n en avaient aucun (btp_chantier, portail cote ERP).
        # 47 -> 49 : le lot du 13/08/2026 ajoute deux modules frontend NEUFS
        # (cpq, segment /cpq/* ; core, module « DONNEES », segment /donnees/*).
        self.assertEqual(stats["configs"], 49)

    def test_parametres_achats_est_desormais_navigable(self):
        """PACT150 : cas vivant du 07/08/2026 — `AchatsParametresPage` (182
        lignes, WIR26) etait routee sans aucune entree de nav ni lien entrant
        reel. Corrige par un `nav.items` dans `features/parametres/
        module.config.jsx` — ce test verrouille la reparation, pas seulement
        l'absence de rouge (que `test_la_base_de_reference_couvre_le_passif`
        prouve deja generiquement)."""
        constats, _ = analyse_reelle()
        sans_nav = {c[1] for c in constats if c[0] == "sans-nav"}
        self.assertNotIn(
            "frontend/src/features/parametres/module.config.jsx::"
            "/parametres/achats", sans_nav)

    def test_le_passif_sans_nav_ne_peut_que_diminuer(self):
        """4 routes reelles restent sans nav le 07/08/2026 (triage PACT150,
        chacune verifiee a la main) : `/admin/impersonation` (consentement
        d'impersonation, atteint par un lien externe hors code frontend),
        `/admin/tenants` (console fondateur SCA22, deliberement hors menu),
        `/credit/conditions` et `/reporting/dashboards` (ecrans reels sans
        entree de menu, dette pre-existante, hors perimetre de cette tache).
        Meme discipline de « sens de variation » que le passif AO : ce compte
        ne doit jamais REMONTER."""
        constats, _ = analyse_reelle()
        sans_nav = [c for c in constats if c[0] == "sans-nav"]
        self.assertLessEqual(
            len(sans_nav), 4,
            "le nombre de routes sans nav a AUGMENTE depuis le passif mesure "
            "le 07/08/2026 (4) : une route reelle a ete livree sans etre "
            "reliee au menu",
        )

    def test_la_base_de_reference_couvre_le_passif(self):
        """Le passif est GELE : sur un depot propre, la garde est verte."""
        constats, _ = analyse_reelle()
        base = cea.charger_base()
        nouveaux = [cea.signature(c) for c in constats
                    if cea.signature(c) not in base]
        self.assertEqual(nouveaux, [])


if __name__ == "__main__":
    unittest.main()
