"""Tests de scripts/reparer_mojibake.py et garde « guide sans mojibake » (ACAL334).

    python -m unittest scripts.tests.test_reparer_mojibake -v

Stdlib pure, aucun Django, aucune base. La garde lit le vrai
docs/GUIDE_UTILISATEUR_ERP.md et echoue a vie si du mojibake (UTF-8 relu comme
cp1252) y revient.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import reparer_mojibake as rm  # noqa: E402 — après sys.path/setup() (D-ENF22)

GUIDE = ROOT / "docs" / "GUIDE_UTILISATEUR_ERP.md"
MOJIBAKE = re.compile("Ã|â€|Â")


def _abime(texte):
    """Simule la corruption : UTF-8 relu comme cp1252."""
    return texte.encode("utf-8").decode("cp1252", errors="strict")


class ReparerLigneTest(unittest.TestCase):
    def test_aller_retour_accents_tirets_guillemets(self):
        for sain in ("données", "— tiret ’ apostrophe", "« citation »",
                     "espace insécable", "à partir de l'étude"):
            self.assertEqual(rm.reparer_ligne(_abime(sain)), sain)

    def test_ligne_saine_ou_irreductible_est_laissee(self):
        self.assertIsNone(rm.reparer_ligne("données correctes"))
        self.assertIsNone(rm.reparer_ligne("ASCII seul"))
        self.assertIsNone(rm.reparer_ligne("Ã seul puis texte"))  # UTF-8 invalide

    def test_bom_conserve(self):
        self.assertEqual(rm.reparer_ligne("﻿" + _abime("généré")),
                         "﻿généré")

    def test_traiter_ne_touche_que_les_lignes_abimees_et_garde_les_fins_de_ligne(self):
        sain = "ligne saine éà\r\n"
        entree = (sain + _abime("réparée") + "\r\nsans marqueur\nÃ irréductible").encode("utf-8")
        sortie, reparees, laissees = rm.traiter(entree)
        self.assertEqual(reparees, 1)
        self.assertEqual([no for no, _ in laissees], [4])
        self.assertEqual(sortie.decode("utf-8"),
                         sain + "réparée\r\nsans marqueur\nÃ irréductible")

    def test_check_detecte_et_ne_modifie_pas(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.md"
            f.write_bytes(_abime("données").encode("utf-8") + b"\n")
            avant = f.read_bytes()
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "reparer_mojibake.py"),
                                "--check", str(f)], capture_output=True)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(f.read_bytes(), avant)


class GuideSansMojibakeTest(unittest.TestCase):
    """Garde a vie : le guide utilisateur ne doit jamais contenir de mojibake."""

    def test_aucune_ligne_ne_contient_de_mojibake(self):
        texte = GUIDE.read_bytes().decode("utf-8")  # leve si le fichier n'est pas de l'UTF-8 valide
        fautives = [no for no, ligne in enumerate(texte.split("\n"), start=1)
                    if MOJIBAKE.search(ligne)]
        self.assertEqual(fautives, [],
                         "mojibake dans %s (l. %s...) : lancer python scripts/reparer_mojibake.py"
                         % (GUIDE.name, fautives[:10]))

    def test_le_script_ne_trouve_plus_rien_a_reparer(self):
        _, reparees, laissees = rm.traiter(GUIDE.read_bytes())
        self.assertEqual((reparees, laissees), (0, []))


if __name__ == "__main__":
    unittest.main()
