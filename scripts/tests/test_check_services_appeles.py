"""Tests de scripts/check_services_appeles.py (garde « service sans appelant »).

Stdlib pur (unittest), aucune base de donnees, aucun import du projet :
    python -m unittest scripts.tests.test_check_services_appeles -v

Chaque test verrouille l'une des deux moities d'une garde utile. La DETECTION
d'abord : une fonction publique de `services/` que personne n'appelle doit
rougir — c'est la maladie mesuree (des milliers de lignes ecrites, testees,
fusionnees, jamais executees). Le SILENCE ensuite, qui compte autant : un
service appele par une vue, par une tache ou par un autre service ne doit
JAMAIS rougir, et une fonction privee (`_`) ne promet rien a personne. Une
garde qui crie au loup est desactivee dans la semaine.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_services_appeles as csa  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FauxBackend:
    """Arborescence `backend/django_core` jetable, branchee sur les
    constantes du module (jamais le vrai depot, jamais la vraie base)."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.django = self.racine / "backend" / "django_core"
        self.app = self.django / "apps" / "x"
        (self.app / "services").mkdir(parents=True)
        self.base = self.racine / "scripts" / "allow.txt"
        self.base.parent.mkdir(parents=True, exist_ok=True)
        self._sauvegarde = (csa.ROOT, csa.DJANGO, csa.BASELINE_PATH,
                            csa.APPS_SURVEILLEES)
        csa.ROOT = self.racine
        csa.DJANGO = self.django
        csa.BASELINE_PATH = self.base
        csa.APPS_SURVEILLEES = ("x",)

    def service(self, nom: str, contenu: str) -> Path:
        return write(self.app / "services" / nom, contenu)

    def fichier(self, relatif: str, contenu: str) -> Path:
        return write(self.app / relatif, contenu)

    def close(self):
        (csa.ROOT, csa.DJANGO, csa.BASELINE_PATH,
         csa.APPS_SURVEILLEES) = self._sauvegarde
        self.tmp.cleanup()


class BaseBackend(unittest.TestCase):
    def setUp(self):
        self.depot = FauxBackend()
        self.addCleanup(self.depot.close)

    def sans_appelant(self):
        constats, _ = csa.analyse()
        return sorted(c[2] for c in constats)


# ===========================================================================
# Detection
# ===========================================================================

class DetectionTests(BaseBackend):
    def test_fonction_publique_sans_aucun_appelant(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self.assertEqual(self.sans_appelant(), ["calculer"])

    def test_la_facade_ne_compte_PAS_comme_appelant(self):
        """Le coeur du sujet : `services/__init__.py` reexporte tout. S'il
        comptait, chaque fonction se justifierait elle-meme et la garde ne
        verrait jamais rien."""
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        write(self.depot.app / "services" / "__init__.py",
              "from .calcul import calculer\n"
              "__all__ = ['calculer']\n"
              "def facade(x):\n    return calculer(x)\n")
        self.assertEqual(self.sans_appelant(), ["calculer"])

    def test_usage_interne_au_module_ne_compte_pas(self):
        """« Qui CONSOMME ce service ? » — un usage dans son propre fichier
        n'y repond pas : c'est le signe d'un helper qui devrait porter `_`."""
        self.depot.service("calcul.py", (
            "def calculer(x):\n    return x\n"
            "def entree(x):\n    return calculer(x)\n"))
        self.depot.fichier("views.py", "from .services.calcul import entree\n"
                                       "def vue(r):\n    return entree(1)\n")
        self.assertEqual(self.sans_appelant(), ["calculer"])

    def test_un_test_n_est_pas_un_appelant(self):
        """Un service appele UNIQUEMENT par ses tests est exactement la
        maladie : le test prouve qu'il marche, personne ne prouve qu'il sert."""
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        write(self.depot.app / "tests" / "test_calcul.py",
              "from ..services.calcul import calculer\n"
              "def test_ok():\n    assert calculer(1) == 1\n")
        self.assertEqual(self.sans_appelant(), ["calculer"])

    def test_un_simple_import_n_est_pas_un_appel(self):
        """Reexporter n'est pas consommer : sans cela, tout module de
        reexport rendrait la garde muette."""
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self.depot.fichier("api.py", "from .services.calcul import calculer\n")
        self.assertEqual(self.sans_appelant(), ["calculer"])


# ===========================================================================
# Silence (anti-faux-positif)
# ===========================================================================

class SilenceTests(BaseBackend):
    def test_appel_depuis_une_vue(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self.depot.fichier("views.py", (
            "from .services.calcul import calculer\n"
            "def vue(requete):\n    return calculer(1)\n"))
        self.assertEqual(self.sans_appelant(), [])

    def test_appel_par_attribut_de_module(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self.depot.fichier("taches.py", (
            "from .services import calcul\n"
            "def tache():\n    return calcul.calculer(1)\n"))
        self.assertEqual(self.sans_appelant(), [])

    def test_passage_en_reference_sans_parenthese(self):
        """`connect(f)`, `{'a': f}` : la fonction sert sans etre appelee ici."""
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self.depot.fichier("receivers.py", (
            "from .services.calcul import calculer\n"
            "TABLE = {'calcul': calculer}\n"))
        self.assertEqual(self.sans_appelant(), [])

    def test_appel_par_un_AUTRE_service(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self.depot.service("pipeline.py", (
            "from .calcul import calculer\n"
            "def enchainer(x):\n    return calculer(x)\n"))
        self.depot.fichier("views.py", (
            "from .services.pipeline import enchainer\n"
            "def vue(r):\n    return enchainer(1)\n"))
        self.assertEqual(self.sans_appelant(), [])

    def test_fonction_privee_ignoree(self):
        self.depot.service("calcul.py", "def _interne(x):\n    return x\n")
        self.assertEqual(self.sans_appelant(), [])

    def test_module_illisible_n_accuse_personne(self):
        """Principe anti-faux-positif : on ignore, on n'accuse jamais."""
        self.depot.service("casse.py", "def calculer(:\n")
        self.assertEqual(self.sans_appelant(), [])

    def test_un_appelant_illisible_n_efface_pas_les_autres(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self.depot.fichier("casse.py", "def vue(:\n    calculer(1)\n")
        self.depot.fichier("views.py", (
            "from .services.calcul import calculer\n"
            "def vue(r):\n    return calculer(1)\n"))
        self.assertEqual(self.sans_appelant(), [])


# ===========================================================================
# Base de reference : elle ne peut que RETRECIR
# ===========================================================================

class BaseDeReferenceTests(BaseBackend):
    def _sortie(self, argv):
        flux = io.StringIO()
        with contextlib.redirect_stdout(flux):
            code = csa.main(argv)
        return code, flux.getvalue()

    def test_une_dette_gelee_ne_rougit_plus(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        code, _ = self._sortie(["--write-baseline"])
        self.assertEqual(code, 0)
        code, sortie = self._sortie([])
        self.assertEqual(code, 0, sortie)

    def test_une_fonction_RETIREE_de_la_base_rougit(self):
        """Le « Done » de la tache : la garde doit rougir sur une fonction
        retiree de la base et rebranchee nulle part."""
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self._sortie(["--write-baseline"])
        csa.ecrire_base(set())          # la ligne quitte la base
        code, sortie = self._sortie([])
        self.assertEqual(code, 1)
        self.assertIn("calculer", sortie)
        self.assertIn("SANS aucun appelant", sortie)

    def test_write_baseline_refuse_de_grossir(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self._sortie(["--write-baseline"])
        self.depot.service("autre.py", "def deuxieme(x):\n    return x\n")
        code, sortie = self._sortie(["--write-baseline"])
        self.assertEqual(code, 1)
        self.assertIn("RETRECIR", sortie)
        self.assertNotIn("deuxieme", csa.charger_base())

    def test_croissance_possible_seulement_avec_le_drapeau(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self._sortie(["--write-baseline"])
        self.depot.service("autre.py", "def deuxieme(x):\n    return x\n")
        code, _ = self._sortie(["--write-baseline", "--autoriser-croissance"])
        self.assertEqual(code, 0)
        self.assertEqual(len(csa.charger_base()), 2)

    def test_une_dette_branchee_quitte_la_base(self):
        self.depot.service("calcul.py", "def calculer(x):\n    return x\n")
        self._sortie(["--write-baseline"])
        self.depot.fichier("views.py", (
            "from .services.calcul import calculer\n"
            "def vue(r):\n    return calculer(1)\n"))
        self._sortie(["--write-baseline"])
        self.assertEqual(csa.charger_base(), set())

    def test_chemin_de_base_resolu_a_l_appel(self):
        """Piege reel du fichier voisin : une valeur par defaut figee a la
        definition ferait ecrire la VRAIE base du depot depuis un test."""
        self.assertIs(csa.charger_base.__defaults__[0], None)
        self.assertIs(csa.ecrire_base.__defaults__[0], None)

    def test_zero_fonction_vue_fait_echouer(self):
        """« OK : 0 » ne doit jamais valoir un vert : la garde aurait cesse
        de garder sans que personne le voie."""
        csa.APPS_SURVEILLEES = ("inexistante",)
        code, sortie = self._sortie([])
        self.assertEqual(code, 1)
        self.assertIn("aucune fonction publique de service", sortie)


# ===========================================================================
# Le depot REEL
# ===========================================================================

class DepotReelTests(unittest.TestCase):
    # UNE seule analyse du vrai backend pour toute la classe : elle relit
    # 60 Mo de source, la refaire par test coute des secondes pour rien.
    @classmethod
    def setUpClass(cls):
        cls.constats, cls.stats = csa.analyse()

    def test_la_garde_est_verte_sur_le_depot(self):
        """La base gele l'etat du jour : sur un depot propre, zero rouge."""
        base = csa.charger_base()
        nouveaux = sorted(c[0] for c in self.constats if c[0] not in base)
        self.assertEqual(nouveaux, [])

    def test_la_garde_voit_vraiment_des_services(self):
        self.assertGreater(self.stats["modules"], 0)
        self.assertGreater(self.stats["fonctions"], 0)

    def test_la_base_committee_ne_gele_que_des_modules_de_services(self):
        for ligne in csa.charger_base():
            module, _, nom = ligne.partition("::")
            self.assertIn("/services/", module, ligne)
            self.assertTrue(nom and not nom.startswith("_"), ligne)


if __name__ == "__main__":
    unittest.main()
