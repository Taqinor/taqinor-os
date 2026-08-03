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
        write(self.src / "main.jsx", "import router from './router'\n")
        self._sauvegarde = (cea.FRONT_SRC, cea.FEATURES, cea.ENTRY, cea.ROOT)
        cea.FRONT_SRC = self.src
        cea.FEATURES = self.features
        cea.ENTRY = self.src / "main.jsx"
        cea.ROOT = Path(self.tmp.name)
        cea._CACHE.clear()

    def fichier(self, relatif: str, contenu: str) -> Path:
        return write(self.src / relatif, contenu)

    def close(self):
        cea.FRONT_SRC, cea.FEATURES, cea.ENTRY, cea.ROOT = self._sauvegarde
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
        return sorted((c[0], c[1]) for c in constats if c[0] != "inatteignable")


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
        """Calepinages/Dossiers cachent un vrai ecran ; Rentabilite non —
        et la garde doit rester MUETTE sur Rentabilite."""
        constats, _ = analyse_reelle()
        routes = sorted(c[1].split("::")[1] for c in constats
                        if c[0] == "bouchon-route")
        self.assertEqual(routes, ["/ao/calepinages", "/ao/dossiers"])

    def test_aucune_config_opaque_sur_le_depot(self):
        """Si une config devient illisible, la garde s'aveugle en silence."""
        _, stats = analyse_reelle()
        self.assertEqual(stats["opaques"], 0)
        self.assertEqual(stats["configs"], 44)

    def test_la_base_de_reference_couvre_le_passif(self):
        """Le passif est GELE : sur un depot propre, la garde est verte."""
        constats, _ = analyse_reelle()
        base = cea.charger_base()
        nouveaux = [cea.signature(c) for c in constats
                    if cea.signature(c) not in base]
        self.assertEqual(nouveaux, [])


if __name__ == "__main__":
    unittest.main()
