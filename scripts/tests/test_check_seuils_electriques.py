"""Tests de scripts/check_seuils_electriques.py (garde CALX250 — « aucun
seuil electrique n'entre sans source »).

Stdlib pur (unittest), aucune base de donnees, aucun import du projet :
    python -m unittest scripts.tests.test_check_seuils_electriques -v

Trois familles. La DETECTION d'abord : un littteral numerique NEUF (constante
de module ou defaut de champ de dataclass) sans commentaire de provenance
doit rougir en nommant fichier:ligne — c'est exactement le trou mesure sur
``core/electrique/types.py:130,132`` (CALX53 a du le NOMMER en aval, rien
n'empechait un troisieme coefficient d'arriver aussi silencieusement). Le
SILENCE ensuite : un littteral source, une valeur de FORME triviale, un
defaut qui refere une AUTRE constante, un fichier hors perimetre ou absent du
disque ne doivent JAMAIS rougir — une garde qui crie au loup se fait
desactiver dans la semaine. La BASE DE REFERENCE enfin : elle ne peut que
RETRECIR, memes garanties que scripts/check_services_appeles.py.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_seuils_electriques as g  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FauxDepot:
    """Arborescence ``core/electrique`` + ``apps/calepinage/services``
    jetable, branchee sur les constantes du module (jamais le vrai depot)."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        django = self.racine / "backend" / "django_core"
        self.core = django / "core" / "electrique"
        self.services = django / "apps" / "calepinage" / "services"
        self.core.mkdir(parents=True)
        self.services.mkdir(parents=True)
        self.base = (self.racine / "scripts"
                     / "seuils_electriques_exceptions.txt")
        self.base.parent.mkdir(parents=True, exist_ok=True)
        self._sauvegarde = (
            g.ROOT, g.DJANGO, g.CORE_ELECTRIQUE_DIR, g.SERVICES_DIR,
            g.BASELINE_PATH, g.SERVICES_SURVEILLES,
        )
        g.ROOT = self.racine
        g.DJANGO = django
        g.CORE_ELECTRIQUE_DIR = self.core
        g.SERVICES_DIR = self.services
        g.BASELINE_PATH = self.base
        g.SERVICES_SURVEILLES = ("electrique", "cables")

    def core_fichier(self, nom: str, contenu: str) -> Path:
        return write(self.core / nom, contenu)

    def service_fichier(self, nom: str, contenu: str) -> Path:
        """``nom`` SANS ``.py`` — doit figurer dans SERVICES_SURVEILLES pour
        etre lu (sinon ignore, comme un fichier reellement hors perimetre)."""
        return write(self.services / f"{nom}.py", contenu)

    def close(self):
        (g.ROOT, g.DJANGO, g.CORE_ELECTRIQUE_DIR, g.SERVICES_DIR,
         g.BASELINE_PATH, g.SERVICES_SURVEILLES) = self._sauvegarde
        self.tmp.cleanup()


class BaseDepot(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)

    def constats(self):
        constats, _ = g.analyse()
        return constats

    def signatures(self):
        return sorted(c[0] for c in self.constats())


# ===========================================================================
# Detection
# ===========================================================================

class DetectionTests(BaseDepot):
    def test_constante_de_module_neuve_sans_source(self):
        self.depot.core_fichier("cables.py", "SEUIL_X = 1.5\n")
        attendu = ["backend/django_core/core/electrique/cables.py:1"]
        self.assertEqual(self.signatures(), attendu)

    def test_defaut_de_dataclass_neuf_sans_source(self):
        self.depot.core_fichier("cables.py", (
            "from dataclasses import dataclass\n\n"
            "@dataclass(frozen=True)\n"
            "class Spec:\n"
            "    seuil: float = 0.35\n"))
        signatures = self.signatures()
        self.assertEqual(len(signatures), 1)
        self.assertTrue(signatures[0].endswith(":5"))

    def test_litteral_negatif_est_analyse(self):
        """Le cas REEL de la tache : ``-0.27`` s'analyse en AST comme
        ``UnaryOp(USub, Constant(0.27))``, pas comme un ``Constant`` direct —
        une garde qui l'ignorerait laisserait passer exactement le defaut de
        ``core/electrique/types.py`` que CALX250 doit fermer."""
        self.depot.core_fichier("cables.py", (
            "from dataclasses import dataclass\n\n"
            "@dataclass(frozen=True)\n"
            "class Spec:\n"
            "    coeff: float = -0.27\n"))
        self.assertEqual(len(self.signatures()), 1)

    def test_le_message_nomme_fichier_et_ligne(self):
        self.depot.core_fichier("cables.py", "SEUIL_X = 1.5\n")
        flux = io.StringIO()
        with contextlib.redirect_stdout(flux):
            code = g.main([])
        self.assertEqual(code, 1)
        self.assertIn("cables.py:1", flux.getvalue())


# ===========================================================================
# Silence (anti-faux-positif)
# ===========================================================================

class SilenceTests(BaseDepot):
    def test_constante_sourcee_par_une_norme_passe(self):
        self.depot.core_fichier("cables.py", (
            "#: Chute de tension DC (UTE C 15-712-1).\n"
            "SEUIL_X = 1.5\n"))
        self.assertEqual(self.signatures(), [])

    def test_constante_sourcee_par_une_fiche_passe(self):
        self.depot.core_fichier("cables.py", (
            "#: Valeur reprise de la fiche produit constructeur.\n"
            "SEUIL_X = 1.5\n"))
        self.assertEqual(self.signatures(), [])

    def test_decision_fondateur_datee_passe(self):
        self.depot.core_fichier("cables.py", (
            "#: Plancher — decision fondateur 19/08/2026.\n"
            "SEUIL_X = 6.0\n"))
        self.assertEqual(self.signatures(), [])

    def test_decision_fondateur_SANS_date_ne_passe_pas(self):
        """Une decision fondateur non datee n'est pas tracable : elle doit
        rester une dette, pas une source acceptee."""
        self.depot.core_fichier("cables.py", (
            "#: Plancher — decision fondateur.\n"
            "SEUIL_X = 6.0\n"))
        self.assertEqual(len(self.signatures()), 1)

    def test_valeur_de_forme_triviale_jamais_signalee(self):
        self.depot.core_fichier("cables.py", (
            "A = 0\nB = 1\nC = -1\nD = 2\nE = 100\n"
            "F = 0.0\nG = 1.0\nH = -1.0\nI = 2.0\nJ = 100.0\n"))
        self.assertEqual(self.signatures(), [])

    def test_field_default_factory_n_est_pas_un_litteral_invente(self):
        self.depot.core_fichier("cables.py", (
            "from dataclasses import dataclass, field\n\n"
            "@dataclass(frozen=True)\n"
            "class Spec:\n"
            "    valeurs: tuple = field(default_factory=tuple)\n"))
        self.assertEqual(self.signatures(), [])

    def test_defaut_qui_refere_une_autre_constante_n_est_pas_flagge(self):
        """``regime: str = REGIME_TT`` n'est pas un ``Constant`` : ce n'est
        pas un nombre invente sur place, c'est une reference nommee."""
        self.depot.core_fichier("cables.py", (
            "from dataclasses import dataclass\n\n"
            "SEUIL = 3.5  # decision fondateur 19/08/2026\n\n"
            "@dataclass(frozen=True)\n"
            "class Spec:\n"
            "    seuil: float = SEUIL\n"))
        self.assertEqual(self.signatures(), [])

    def test_fichier_hors_liste_services_surveilles_ignore(self):
        write(self.depot.services / "hors_perimetre.py", "SEUIL_X = 1.5\n")
        self.assertEqual(self.signatures(), [])

    def test_service_absent_du_disque_n_echoue_pas(self):
        """Une lane voisine du meme lot construit encore certains fichiers
        (``troncons.py``, ``raccordement.py``…) : leur absence ne doit
        jamais faire planter ni accuser la garde."""
        g.SERVICES_SURVEILLES = ("electrique", "troncons_pas_encore_construit")
        self.depot.service_fichier("electrique", "SEUIL_X = 1.5\n")
        signatures = self.signatures()
        self.assertEqual(len(signatures), 1)
        self.assertIn("electrique.py", signatures[0])

    def test_argument_par_defaut_d_une_fonction_ordinaire_hors_perimetre(self):
        """Le perimetre ecrit par la tache est EXACT : constantes de module
        et defauts de dataclass, jamais les arguments d'une fonction."""
        self.depot.core_fichier("cables.py", (
            "def ampacite(section, temperature=30.5):\n"
            "    return section * temperature\n"))
        self.assertEqual(self.signatures(), [])

    def test_fichier_illisible_n_accuse_personne(self):
        self.depot.core_fichier("casse.py", "SEUIL_X = (\n")
        self.assertEqual(self.signatures(), [])

    def test_paragraphe_partage_deux_constantes_meme_commentaire(self):
        """Motif reel de ``core/electrique/cables.py`` : un seul commentaire
        d'en-tete introduit deux constantes consecutives SANS ligne vide."""
        self.depot.core_fichier("cables.py", (
            "#: Chute de tension DC : cible, maximum (UTE C 15-712-1).\n"
            "CHUTE_CIBLE_PCT = 1.5\n"
            "CHUTE_MAX_PCT = 3.0\n"))
        self.assertEqual(self.signatures(), [])

    def test_champ_de_dataclass_ne_partage_pas_le_commentaire_du_voisin(self):
        """A l'inverse d'une constante de module, un champ de dataclass ne
        remonte QUE son propre commentaire direct — deux champs voisins
        d'une meme classe n'ont pas forcement la meme provenance."""
        self.depot.core_fichier("cables.py", (
            "from dataclasses import dataclass\n\n"
            "@dataclass(frozen=True)\n"
            "class Spec:\n"
            "    #: Cite IEC 62548.\n"
            "    premier: float = 1.25\n"
            "    second: float = 2.4\n"))
        signatures = self.signatures()
        self.assertEqual(len(signatures), 1)
        # `second` (ligne 7) rougit, `premier` (source IEC) non.
        self.assertTrue(signatures[0].endswith(":7"))


# ===========================================================================
# Base de reference : elle ne peut que RETRECIR
# ===========================================================================

class BaseDeReferenceTests(BaseDepot):
    def _sortie(self, argv):
        flux = io.StringIO()
        with contextlib.redirect_stdout(flux):
            code = g.main(argv)
        return code, flux.getvalue()

    def test_une_dette_gelee_ne_rougit_plus(self):
        self.depot.core_fichier("cables.py", "SEUIL_X = 1.5\n")
        code, _ = self._sortie(["--write-baseline"])
        self.assertEqual(code, 0)
        code, sortie = self._sortie([])
        self.assertEqual(code, 0, sortie)

    def test_un_littteral_retire_de_la_base_rougit(self):
        """Le Done de CALX250 : l'ajout d'un littteral non source (ou son
        retrait de la base) fait echouer la garde en nommant fichier:ligne."""
        self.depot.core_fichier("cables.py", "SEUIL_X = 1.5\n")
        self._sortie(["--write-baseline"])
        g.ecrire_base({})
        code, sortie = self._sortie([])
        self.assertEqual(code, 1)
        self.assertIn("cables.py:1", sortie)

    def test_write_baseline_refuse_de_grossir(self):
        self.depot.core_fichier("cables.py", "SEUIL_X = 1.5\n")
        self._sortie(["--write-baseline"])
        self.depot.core_fichier("protections.py", "SEUIL_Y = 2.5\n")
        code, sortie = self._sortie(["--write-baseline"])
        self.assertEqual(code, 1)
        self.assertIn("RETRECIR", sortie)
        self.assertNotIn("protections.py", "".join(g.charger_base()))

    def test_croissance_possible_seulement_avec_le_drapeau(self):
        self.depot.core_fichier("cables.py", "SEUIL_X = 1.5\n")
        self._sortie(["--write-baseline"])
        self.depot.core_fichier("protections.py", "SEUIL_Y = 2.5\n")
        code, _ = self._sortie(["--write-baseline", "--autoriser-croissance"])
        self.assertEqual(code, 0)
        self.assertEqual(len(g.charger_base()), 2)

    def test_une_dette_sourcee_quitte_la_base(self):
        self.depot.core_fichier("cables.py", "SEUIL_X = 1.5\n")
        self._sortie(["--write-baseline"])
        self.depot.core_fichier("cables.py", (
            "#: Desormais cite (NF C 15-100).\nSEUIL_X = 1.5\n"))
        self._sortie(["--write-baseline"])
        self.assertEqual(g.charger_base(), {})

    def test_write_baseline_conserve_le_motif_ecrit_a_la_main(self):
        """Le motif est ecrit par un humain (ou par CALX250 pour les deux
        coefficients de types.py) : un ``--write-baseline`` qui tourne plus
        tard ne doit PAS l'ecraser par un motif generique recalcule tant que
        le littteral reste dans la base."""
        self.depot.core_fichier("cables.py", "SEUIL_X = 1.5\n")
        write(self.depot.base,
              g.ENTETE_BASE +
              "backend/django_core/core/electrique/cables.py:1"
              "  # motif ecrit a la main, a conserver\n")
        self._sortie(["--write-baseline"])
        base = g.charger_base()
        self.assertEqual(
            base["backend/django_core/core/electrique/cables.py:1"],
            "motif ecrit a la main, a conserver")

    def test_chemin_de_base_resolu_a_l_appel(self):
        """Meme piege que check_services_appeles.py : une valeur par defaut
        figee a la definition ecrirait dans la VRAIE base du depot."""
        self.assertIs(g.charger_base.__defaults__[0], None)
        self.assertIs(g.ecrire_base.__defaults__[0], None)

    def test_zero_fichier_lu_fait_echouer(self):
        """« OK : 0 » ne doit jamais valoir un vert : la garde aurait cesse
        de garder sans que personne le voie."""
        g.SERVICES_SURVEILLES = ()
        import shutil
        shutil.rmtree(self.depot.core)
        code, sortie = self._sortie([])
        self.assertEqual(code, 1)
        self.assertIn("aucun fichier lu", sortie)


# ===========================================================================
# Le depot REEL
# ===========================================================================

class DepotReelTests(unittest.TestCase):
    # UNE seule analyse du vrai backend pour toute la classe.
    @classmethod
    def setUpClass(cls):
        cls.constats, cls.stats = g.analyse()

    def test_la_garde_est_verte_sur_le_depot(self):
        """La base gele l'etat du jour : sur le depot commite, zero rouge."""
        base = g.charger_base()
        nouveaux = sorted(c[0] for c in self.constats if c[0] not in base)
        self.assertEqual(nouveaux, [])

    def test_la_garde_voit_vraiment_des_litteraux(self):
        self.assertGreater(self.stats["fichiers"], 0)
        total = (self.stats["constantes_module"]
                 + self.stats["defauts_dataclass"])
        self.assertGreater(total, 0)

    def test_les_deux_coefficients_de_types_py_sont_geles(self):
        """Le Done explicite de CALX250 : les deux coefficients de
        ``types.py`` figurent dans la base avec leur motif dedie."""
        base = g.charger_base()
        cle_voc = "backend/django_core/core/electrique/types.py:130"
        cle_pmax = "backend/django_core/core/electrique/types.py:132"
        self.assertIn(cle_voc, base)
        self.assertIn(cle_pmax, base)
        motif = "défaut non sourcé, à remplacer par une fiche"
        self.assertIn(motif, base[cle_voc])
        self.assertIn(motif, base[cle_pmax])

    def test_la_base_committee_ne_gele_que_le_perimetre(self):
        for cle in g.charger_base():
            fichier, _, ligne = cle.rpartition(":")
            self.assertTrue(ligne.isdigit(), cle)
            self.assertTrue(
                "/core/electrique/" in fichier
                or "/apps/calepinage/services/" in fichier,
                cle)


if __name__ == "__main__":
    unittest.main()
