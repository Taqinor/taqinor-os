"""CALX56 — chemins A SEGMENT DYNAMIQUE dans la garde d'atteignabilite.

Stdlib pur (unittest), aucune base de donnees, aucun node, aucun build :
    python -m unittest scripts.tests.test_check_ecrans_parametres -v

POURQUOI CE FICHIER EXISTE. ``check_ecrans_atteignables.py`` exemptait EN BLOC
tout chemin contenant ``:`` (« segment dynamique : exempte »). C'est par ce
trou que treize chemins ``/calepinage/:id/<x>`` ont pu vivre sans le moindre
lien entrant sans jamais rougir, et que ``scripts/ecrans_atteignables_allow.txt``
ne portait aucune ligne ``calepinage``. Les tests ci-dessous verrouillent les
DEUX moities de la reparation, et la seconde compte autant que la premiere :

  * le POUVOIR DE DETECTION — un chemin parametre sans aucun lien entrant est
    signale ;
  * le SILENCE — un chemin parametre vise par un lien a gabarit
    (`` to={`/a/${x}/b`} ``, `` navigate(...) ``), par une entree declaree
    ailleurs, ou par le marqueur ``// contextuelle:`` ne l'est PAS. Une garde
    qui crie au loup est desactivee dans la semaine ; c'est le principe
    anti-faux-positif que porte deja l'en-tete du script.

Le harnais de depot jetable (``FauxDepot``/``BaseDepot``) est celui du fichier
de tests voisin : le dupliquer ferait deux verites a maintenir.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_ecrans_atteignables as cea  # noqa: E402

from .test_check_ecrans_atteignables import BaseDepot  # noqa: E402


# ===========================================================================
# Le gabarit : la FORME d'un chemin, segment par segment
# ===========================================================================

class GabaritTests(unittest.TestCase):
    def test_segment_inconnu_des_deux_ecritures(self):
        """`:id` (route) et `${x}` (lien) sont le MEME inconnu."""
        self.assertEqual(cea.gabarit("/a/:id/b"), ["", "a", None, "b"])
        self.assertEqual(cea.gabarit("/a/${x}/b"), ["", "a", None, "b"])

    def test_la_query_et_l_ancre_ne_comptent_pas(self):
        self.assertEqual(cea.gabarit("/a/:id?onglet=x#haut"),
                         ["", "a", None])

    def test_correspondance_des_deux_cotes(self):
        self.assertTrue(cea.correspond("/a/:id/b", "/a/${x}/b"))
        # Un litteral CONCRET mene lui aussi a la route parametree.
        self.assertTrue(cea.correspond("/a/:id/b", "/a/42/b"))
        # Un segment inconnu du cote du LIEN accepte une route litterale.
        self.assertTrue(cea.correspond("/a/b", "/a/${x}"))

    def test_ce_qui_ne_correspond_PAS(self):
        self.assertFalse(cea.correspond("/a/:id/b", "/a/b"))        # longueur
        self.assertFalse(cea.correspond("/a/:id/b", "/a/42/c"))     # dernier
        self.assertFalse(cea.correspond("/a/:id/b", "/z/42/b"))     # premier


# ===========================================================================
# La classe 3 sur un module jetable
# ===========================================================================

class RouteParametreeTests(BaseDepot):
    def _config(self, app: str, chemin: str, extra_nav: str = "") -> Path:
        return self.depot.fichier(f"features/{app}/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            f"const config = {{ key:'{app}', nav: {{ label:'{app}', items: ["
            f"{extra_nav}] }}, routes: [{{ path:'{chemin}', component: Ecran }}] }}\n"
            "export default config\n"))

    def test_chemin_parametre_sans_lien_entrant_est_DETECTE(self):
        """Le controle negatif : exactement le cas `/calepinage/:id/<x>`.

        La route est ECRITE dans ce module.config.jsx — la garde ne doit pas
        s'auto-verifier en trouvant sa propre declaration.
        """
        self._config("x", "/x/:id/rapport")
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.assertEqual(
            self.sans_nav(),
            ["frontend/src/features/x/module.config.jsx::/x/:id/rapport"])

    def test_chemin_parametre_lie_par_gabarit_est_MUET(self):
        """`` navigate(`/x/${id}/rapport`) `` dans un fichier atteignable."""
        self._config("x", "/x/:id/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Barre from './Barre'\nexport default 1\n")
        self.depot.fichier("features/x/Barre.jsx", (
            "export default ({ id }) => "
            "<button onClick={() => navigate(`/x/${id}/rapport`)}>R</button>\n"))
        self.assertEqual(self.sans_nav(), [])

    def test_gabarit_dans_un_Link_est_MUET(self):
        self._config("x", "/x/:id/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Barre from './Barre'\nexport default 1\n")
        self.depot.fichier("features/x/Barre.jsx", (
            "export default ({ id }) => "
            "<Link to={`/x/${id}/rapport`}>R</Link>\n"))
        self.assertEqual(self.sans_nav(), [])

    def test_gabarit_qui_vise_une_AUTRE_route_ne_justifie_pas(self):
        """Le gabarit compare segment a segment : `/x/${id}/autre` ne dit
        rien de `/x/:id/rapport`."""
        self._config("x", "/x/:id/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Barre from './Barre'\nexport default 1\n")
        self.depot.fichier("features/x/Barre.jsx", (
            "export default ({ id }) => "
            "<Link to={`/x/${id}/autre`}>A</Link>\n"))
        self.assertEqual(
            self.sans_nav(),
            ["frontend/src/features/x/module.config.jsx::/x/:id/rapport"])

    def test_gabarit_dans_un_fichier_MORT_ne_compte_pas(self):
        """Meme regle que pour les litteraux : un lien ecrit dans un composant
        que rien n'atteint ne rend rien reel."""
        self._config("x", "/x/:id/rapport")
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/x/Mort.jsx", (
            "export default ({ id }) => "
            "<Link to={`/x/${id}/rapport`}>R</Link>\n"))
        self.assertEqual(
            self.sans_nav(),
            ["frontend/src/features/x/module.config.jsx::/x/:id/rapport"])

    def test_gabarit_dans_un_TEST_ne_compte_pas(self):
        self._config("x", "/x/:id/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Barre from './Barre'\nexport default 1\n")
        self.depot.fichier("features/x/Barre.jsx", "export default 1\n")
        self.depot.fichier("features/x/Barre.test.jsx", (
            "it('ouvre', () => render(<Link to={`/x/${id}/rapport`}/>))\n"))
        self.assertEqual(
            self.sans_nav(),
            ["frontend/src/features/x/module.config.jsx::/x/:id/rapport"])

    def test_nav_item_a_gabarit_d_un_AUTRE_module_compte(self):
        """« une entree declaree ailleurs » : seuls `to`/`href` comptent dans
        un module.config.jsx — jamais `path`, qui s'auto-justifierait."""
        self._config("x", "/x/:id/rapport")
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/y/module.config.jsx", (
            "const config = { key:'y', nav: { label:'y', items: ["
            "{ to: `/x/${courant}/rapport`, label: 'Rapport' }"
            "] }, routes: [] }\nexport default config\n"))
        self.assertEqual(self.sans_nav(), [])

    def test_le_path_parametre_ne_s_auto_justifie_pas(self):
        """Deux routes parametrees dans la MEME config : aucune ne justifie
        l'autre, et aucune ne se justifie elle-meme."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const Autre = lazy(() => import('./Autre'))\n"
            "const config = { key:'x', nav: { label:'x', items: [] }, routes: [\n"
            "  { path:'/x/:id/rapport', component: Ecran },\n"
            "  { path:'/x/:id/autre', component: Autre },\n"
            "] }\nexport default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.depot.fichier("features/x/Autre.jsx", "export default 1\n")
        self.assertEqual(self.sans_nav(), [
            "frontend/src/features/x/module.config.jsx::/x/:id/autre",
            "frontend/src/features/x/module.config.jsx::/x/:id/rapport",
        ])

    def test_marqueur_contextuel_justifie_un_chemin_parametre(self):
        """La troisieme sortie, inchangee : une route volontairement hors
        menu se declare, elle ne se cache pas."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const config = { key:'x', nav: { label:'x', items: [] }, routes: [\n"
            "  { path:'/x/:id/rapport', component: Ecran }, "
            "// contextuelle: lien envoye au client par message\n"
            "] }\nexport default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")
        self.assertEqual(self.sans_nav(), [])

    def test_une_route_litterale_reste_jugee_a_l_identique(self):
        """Aucune regression de la classe 3 historique : l'egalite exacte
        reste la regle pour un chemin sans segment dynamique."""
        self._config("x", "/x/rapport")
        self.depot.fichier("features/x/Ecran.jsx",
                           "import Barre from './Barre'\nexport default 1\n")
        self.depot.fichier("features/x/Barre.jsx",
                           "export default () => <Link to=\"/x/rapport\">R</Link>\n")
        self.assertEqual(self.sans_nav(), [])


# ===========================================================================
# Base de reference : elle ne peut que retrecir
# ===========================================================================

class BaseParametreeTests(BaseDepot):
    def test_un_chemin_parametre_gele_ne_rougit_plus(self):
        """La base absorbe la dette du jour : la garde empeche la RECIDIVE,
        elle ne repare pas le passif."""
        self.depot.fichier("features/x/module.config.jsx", (
            "const Ecran = lazy(() => import('./Ecran'))\n"
            "const config = { key:'x', nav: { label:'x', items: [] }, "
            "routes: [{ path:'/x/:id/rapport', component: Ecran }] }\n"
            "export default config\n"))
        self.depot.fichier("features/x/Ecran.jsx", "export default 1\n")

        constats, _ = cea.analyse()
        signature = ("sans-nav|frontend/src/features/x/module.config.jsx"
                     "::/x/:id/rapport")
        self.assertIn(signature, {cea.signature(c) for c in constats})
        nouveaux = [c for c in constats
                    if cea.signature(c) not in {signature}]
        self.assertEqual([c for c in nouveaux if c[0] == "sans-nav"], [])


class BaseReelleTests(unittest.TestCase):
    """Le depot REEL : la dette parametree du jour est GELEE, pas cachee."""

    def test_la_base_committee_porte_la_dette_parametree(self):
        base = cea.charger_base()
        parametrees = [ligne for ligne in base
                       if ligne.startswith("sans-nav|") and ":" in
                       ligne.partition("::")[2]]
        self.assertTrue(
            parametrees,
            "la base ne gele aucun chemin parametre : soit la reparation "
            "CALX56 est defaite, soit la base n'a pas ete ecrite",
        )


if __name__ == "__main__":
    unittest.main()
