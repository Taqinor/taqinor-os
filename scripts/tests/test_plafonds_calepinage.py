"""ACAL339 - les trois passifs calepinage sont figes a decroissance forcee.

Stdlib pur (unittest), aucune base de donnees :
    python -m unittest scripts.tests.test_plafonds_calepinage -v

Passifs : scripts/services_appeles_allow.txt (lignes apps/calepinage/),
scripts/calepinage_actions_allow.txt, scripts/frontiere_calepinage_allow.txt.
Plafonds : scripts/plafonds_calepinage.json (ne fait que baisser).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
PLAFONDS = SCRIPTS / "plafonds_calepinage.json"
BASES = {
    "services_appeles": ("services_appeles_allow.txt", "apps/calepinage/"),
    "actions": ("calepinage_actions_allow.txt", ""),
    "frontiere": ("frontiere_calepinage_allow.txt", ""),
}


def lignes_de_base(texte: str, filtre: str = "") -> list:
    """Lignes de dette : ni vides ni commentaires, filtrees par sous-chaine."""
    return [ligne.strip() for ligne in texte.splitlines()
            if ligne.strip() and not ligne.lstrip().startswith("#")
            and filtre in ligne]


def comptes_reels() -> dict:
    return {
        cle: len(lignes_de_base((SCRIPTS / fichier).read_text(encoding="utf-8"), filtre))
        for cle, (fichier, filtre) in BASES.items()
    }


def depassements(comptes: dict, plafonds: dict) -> list:
    return [cle for cle in BASES if comptes[cle] > plafonds[cle]]


class PlafondsCalepinageTest(unittest.TestCase):

    def setUp(self):
        self.plafonds = json.loads(PLAFONDS.read_text(encoding="utf-8"))

    def test_les_passifs_ne_depassent_pas_leur_plafond(self):
        self.assertEqual(depassements(comptes_reels(), self.plafonds), [])

    def test_une_ligne_de_plus_depasse_le_plafond(self):
        """Test-du-test : une ligne fictive ajoutee a une copie de la base."""
        fichier, filtre = BASES["services_appeles"]
        texte = (SCRIPTS / fichier).read_text(encoding="utf-8")
        texte += "\napps/calepinage/services/x.py::fonction_fictive\n"
        comptes = comptes_reels()
        comptes["services_appeles"] = len(lignes_de_base(texte, filtre))
        self.assertEqual(depassements(comptes, self.plafonds), ["services_appeles"])

    def test_le_plafond_egale_le_compte_reel(self):
        self.assertEqual(set(self.plafonds) - {"_note"}, set(BASES))
        reels = comptes_reels()
        for cle in BASES:
            with self.subTest(passif=cle):
                self.assertEqual(
                    self.plafonds[cle], reels[cle],
                    "le plafond suit la base a la baisse : le baisser dans le "
                    "meme commit que --write-baseline")


if __name__ == "__main__":
    unittest.main()
