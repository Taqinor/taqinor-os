"""Tests de scripts/check_calepinage_provenance_constantes.py (CALX384).

Stdlib pur (unittest), aucune base de donnees :
    python -m unittest scripts.tests.test_check_calepinage_provenance_constantes -v

DETECTION : une constante numerique de niveau module SANS aucun commentaire
rougit en la nommant. SILENCE (les deux formes légitimes MESURÉES sur le vrai
dépôt, `thermique.py`/`pompage.py`/`electrique.py`) : un commentaire
directement au-dessus, ET le commentaire de TÊTE d'un bloc contigu de trois
constantes (la 2e et la 3e n'ont AUCUN commentaire à elles, seule la 1re
touche le `#:` de tête — exactement le patron qui produit un faux positif
sous une lecture naïve « la ligne du dessus »).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_calepinage_provenance_constantes as cpc  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FauxPaquet:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.services = self.racine / "backend" / "django_core" / "apps" / "calepinage" / "services"
        self.services.mkdir(parents=True)
        self._sauvegarde = (cpc.ROOT, cpc.SERVICES_DIR)
        cpc.ROOT = self.racine
        cpc.SERVICES_DIR = self.services

    def module(self, nom: str, contenu: str) -> Path:
        return write(self.services / nom, contenu)

    def close(self):
        cpc.ROOT, cpc.SERVICES_DIR = self._sauvegarde
        self.tmp.cleanup()


class BasePaquet(unittest.TestCase):
    def setUp(self):
        self.depot = FauxPaquet()
        self.addCleanup(self.depot.close)


# ===========================================================================
# Detection
# ===========================================================================

class DetectionTests(BasePaquet):
    def test_constante_numerique_nue_est_nommee(self):
        self.depot.module("x.py", "SEUIL_MAX = 42\n")
        constats = cpc.constantes_sans_provenance(self.depot.services / "x.py")
        self.assertEqual(constats, [(1, "SEUIL_MAX")])

    def test_constante_dans_un_tuple_nu_est_detectee(self):
        self.depot.module("x.py", "NOMBRES = (0, 1, 2)\n")
        constats = cpc.constantes_sans_provenance(self.depot.services / "x.py")
        self.assertEqual(constats, [(1, "NOMBRES")])

    def test_ligne_blanche_casse_la_chaine(self):
        self.depot.module("x.py", (
            "#: Provenance de A.\n"
            "SEUIL_A = 1\n"
            "\n"
            "SEUIL_B = 2\n"
        ))
        constats = cpc.constantes_sans_provenance(self.depot.services / "x.py")
        self.assertEqual(constats, [(4, "SEUIL_B")])

    def test_main_rend_1_et_nomme_fichier_ligne_et_constante(self):
        import contextlib
        import io
        self.depot.module("x.py", "SEUIL_MAX = 42\n")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = cpc.main([])
        self.assertEqual(code, 1)
        texte = sortie.getvalue()
        self.assertIn("x.py:1", texte)
        self.assertIn("SEUIL_MAX", texte)


# ===========================================================================
# Silence — les DEUX formes légitimes mesurées sur le vrai dépôt
# ===========================================================================

class SilenceTests(BasePaquet):
    def test_commentaire_directement_au_dessus(self):
        self.depot.module("x.py", (
            "#: Le seuil maximal admis par la fiche constructeur.\n"
            "SEUIL_MAX = 42\n"
        ))
        constats = cpc.constantes_sans_provenance(self.depot.services / "x.py")
        self.assertEqual(constats, [])

    def test_commentaire_de_tete_dun_bloc_de_trois_constantes(self):
        # Patron mesuré : thermique.py (NOCT_IRRADIANCE_W_M2 puis
        # NOCT_TEMPERATURE_AIR_C, seule la première touche le `#:` de tête).
        self.depot.module("x.py", (
            "#: Trois seuils de la même famille, une seule tête de bloc.\n"
            "SEUIL_A = 1\n"
            "SEUIL_B = 2\n"
            "SEUIL_C = 3\n"
        ))
        constats = cpc.constantes_sans_provenance(self.depot.services / "x.py")
        self.assertEqual(constats, [])

    def test_constante_non_numerique_nest_jamais_concernee(self):
        self.depot.module("x.py", "MODE = 'auto'\n")
        constats = cpc.constantes_sans_provenance(self.depot.services / "x.py")
        self.assertEqual(constats, [])

    def test_maillon_intermediaire_non_numerique_transmet_la_provenance(self):
        # Patron mesuré : electrique.py — ORIGINE_* (chaînes) entre deux
        # blocs numériques n'est pas ce cas précis, mais un maillon NON
        # numérique dans la MÊME chaîne contiguë doit quand même relayer le
        # commentaire de tête jusqu'au maillon numérique qui suit.
        self.depot.module("x.py", (
            "#: Tête de bloc couvrant AUSSI un maillon non numérique.\n"
            "MODE_PAR_DEFAUT = 'auto'\n"
            "SEUIL_MAX = 42\n"
        ))
        constats = cpc.constantes_sans_provenance(self.depot.services / "x.py")
        self.assertEqual(constats, [])

    def test_fichier_reel_thermique_ne_rougit_pas(self):
        # Non-régression : le patron EXACT qui a motivé la garde.
        self.depot.module("thermique.py", (
            "#: Irradiance de définition de la NOCT (W/m²) et température "
            "d'air associée —\n"
            "#: ce sont les conditions NOCT elles-mêmes, pas des réglages.\n"
            "NOCT_IRRADIANCE_W_M2 = 800.0\n"
            "NOCT_TEMPERATURE_AIR_C = 20.0\n"
        ))
        constats = cpc.constantes_sans_provenance(self.depot.services / "thermique.py")
        self.assertEqual(constats, [])


# ===========================================================================
# main() global
# ===========================================================================

class MainTests(BasePaquet):
    def test_paquet_propre_rend_0(self):
        self.depot.module("x.py", "#: provenance.\nSEUIL = 1\n")
        self.assertEqual(cpc.main([]), 0)

    def test_deux_fichiers_une_seule_faute_est_nommee(self):
        self.depot.module("propre.py", "#: provenance.\nSEUIL = 1\n")
        self.depot.module("fautif.py", "SEUIL_NU = 2\n")
        import contextlib
        import io
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = cpc.main([])
        self.assertEqual(code, 1)
        self.assertIn("fautif.py:1", sortie.getvalue())
        self.assertNotIn("propre.py", sortie.getvalue())


if __name__ == "__main__":
    unittest.main()
