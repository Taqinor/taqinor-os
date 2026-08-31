"""Tests de scripts/check_modes_marche.py (QJR231).

Stdlib pur (unittest), aucune base de donnees, aucun Django, aucun node.
Lancer :
    python -m unittest scripts.tests.test_check_modes_marche -v

Les tests qui comptent sont les NEGATIFS EXECUTES : un mode retire d'UN SEUL
des six sites doit rougir, en NOMMANT ce site et le mode manquant. Une garde
de parite qu'on n'a jamais vue rougir ne prouve rien.
"""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_modes_marche as guard  # noqa: E402

QUATRE_MODES = ["residentiel", "industriel", "commercial", "agricole"]

# --- fixtures FIDELES aux six sites reels (memes formes AST/regex) ----------

REDUCTEUR_OK = "export const MODES = ['residentiel', 'industriel', 'commercial', 'agricole']\n"
REDUCTEUR_INCOMPLET = "export const MODES = ['residentiel', 'industriel', 'commercial']\n"

PANNEAUX_OK = (
    "const MODE_OPTIONS = [\n"
    "  { value: 'residentiel', label: '\U0001F3E0 Résidentiel' },\n"
    "  { value: 'industriel', label: '\U0001F3ED Industriel' },\n"
    "  { value: 'commercial', label: '\U0001F3EA Commercial' },\n"
    "  { value: 'agricole', label: '\U0001F33E Agricole (pompage)' },\n"
    "]\n"
)
PANNEAUX_SURNUMERAIRE = (
    "const MODE_OPTIONS = [\n"
    "  { value: 'residentiel', label: 'R' },\n"
    "  { value: 'industriel', label: 'I' },\n"
    "  { value: 'commercial', label: 'C' },\n"
    "  { value: 'agricole', label: 'A' },\n"
    "  { value: 'tertiaire', label: 'T' },\n"
    "]\n"
)

CLASSIFIEURS_OK = "MODES_INSTALLATION = ('residentiel', 'industriel', 'commercial', 'agricole')\n"

BACKEND_DEVIS_OK = '''
class Devis(models.Model):
    class ModeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        INDUSTRIEL = 'industriel', 'Industriel'
        COMMERCIAL = 'commercial', 'Commercial'
        AGRICOLE = 'agricole', 'Agricole (pompage)'
'''
BACKEND_DEVIS_SANS_AGRICOLE = '''
class Devis(models.Model):
    class ModeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        INDUSTRIEL = 'industriel', 'Industriel'
        COMMERCIAL = 'commercial', 'Commercial'
'''

BACKEND_LEAD_OK = '''
class Lead(SoftDeleteModel):
    class TypeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        COMMERCIAL = 'commercial', 'Commercial'
        INDUSTRIEL = 'industriel', 'Industriel'
        AGRICOLE = 'agricole', 'Agricole'
'''

QUOTE_ENGINE_OK = '_MODES = ("residentiel", "industriel", "commercial", "agricole")\n'


def _contrat_tmp(tmp: Path, modes=None) -> Path:
    p = tmp / "modes_marche.json"
    p.write_text(json.dumps({"modes": modes if modes is not None else QUATRE_MODES}), encoding="utf-8")
    return p


def _six_sites_ok(tmp: Path) -> dict:
    fichiers = {
        "reducteur": ("sizingReducer.js", REDUCTEUR_OK),
        "panneaux": ("DevisGenerator.jsx", PANNEAUX_OK),
        "classifieurs": ("creation.py", CLASSIFIEURS_OK),
        "backend_devis": ("models_ventes.py", BACKEND_DEVIS_OK),
        "backend_lead": ("models_crm.py", BACKEND_LEAD_OK),
        "quote_engine_photos": ("installations.py", QUOTE_ENGINE_OK),
    }
    chemins = {}
    for etiquette, (nom, contenu) in fichiers.items():
        p = tmp / nom
        p.write_text(contenu, encoding="utf-8")
        chemins[etiquette] = p
    return chemins


class ExtractionTests(unittest.TestCase):
    """Chaque extracteur, EXECUTE sur une fixture fidele au site reel."""

    def test_reducteur_js_array(self):
        self.assertEqual(
            guard._extraire_js_array(REDUCTEUR_OK, "MODES"), set(QUATRE_MODES))

    def test_panneaux_mode_options_ne_lit_que_value_jamais_label(self):
        valeurs = guard._extraire_mode_options_values(PANNEAUX_OK)
        self.assertEqual(valeurs, set(QUATRE_MODES))
        # Aucun libellé FR/emoji ne doit fuiter dans l'ensemble comparé.
        for v in valeurs:
            self.assertRegex(v, r"^[a-z_]+$")

    def test_classifieurs_tuple_module(self):
        self.assertEqual(
            guard._extraire_tuple_module(CLASSIFIEURS_OK, "MODES_INSTALLATION"),
            set(QUATRE_MODES))

    def test_backend_devis_text_choices_valeurs_pas_libelles(self):
        self.assertEqual(
            guard._extraire_text_choices(BACKEND_DEVIS_OK, "Devis", "ModeInstallation"),
            set(QUATRE_MODES))

    def test_backend_lead_text_choices(self):
        self.assertEqual(
            guard._extraire_text_choices(BACKEND_LEAD_OK, "Lead", "TypeInstallation"),
            set(QUATRE_MODES))

    def test_quote_engine_tuple_module(self):
        self.assertEqual(
            guard._extraire_tuple_module(QUOTE_ENGINE_OK, "_MODES"), set(QUATRE_MODES))

    def test_site_introuvable_rend_None(self):
        self.assertIsNone(guard._extraire_js_array("const AUTRECHOSE = []", "MODES"))
        self.assertIsNone(guard._extraire_tuple_module("x = 1", "MODES_INSTALLATION"))
        self.assertIsNone(guard._extraire_text_choices("class Autre: pass", "Devis", "ModeInstallation"))


class PariteTests(unittest.TestCase):
    """Les rouges. Chacun est EXECUTE contre de vrais fichiers temporaires."""

    def test_les_six_sites_conformes_ne_produisent_rien(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chemins = _six_sites_ok(tmp_path)
            self.assertEqual(guard.constats(set(QUATRE_MODES), chemins), [])

    def test_UN_MODE_RETIRE_DU_REDUCTEUR_SEUL_ROUGIT(self):
        # LE point de QJR231 : un cinquième marché (ou ici, un marché RETIRÉ)
        # sur un seul site doit se voir — jamais un silence.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chemins = _six_sites_ok(tmp_path)
            chemins["reducteur"].write_text(REDUCTEUR_INCOMPLET, encoding="utf-8")
            trouves = guard.constats(set(QUATRE_MODES), chemins)
            self.assertEqual([site for site, _ in trouves], ["reducteur"])
            self.assertIn("agricole", trouves[0][1])

    def test_UN_MODE_RETIRE_DU_BACKEND_DEVIS_SEUL_ROUGIT(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chemins = _six_sites_ok(tmp_path)
            chemins["backend_devis"].write_text(BACKEND_DEVIS_SANS_AGRICOLE, encoding="utf-8")
            trouves = guard.constats(set(QUATRE_MODES), chemins)
            self.assertEqual([site for site, _ in trouves], ["backend_devis"])
            self.assertIn("agricole", trouves[0][1])

    def test_UN_MODE_SURNUMERAIRE_ROUGIT_AUSSI(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chemins = _six_sites_ok(tmp_path)
            chemins["panneaux"].write_text(PANNEAUX_SURNUMERAIRE, encoding="utf-8")
            trouves = guard.constats(set(QUATRE_MODES), chemins)
            self.assertEqual([site for site, _ in trouves], ["panneaux"])
            self.assertIn("tertiaire", trouves[0][1])

    def test_les_autres_sites_ne_sont_PAS_impliques_par_une_seule_divergence(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chemins = _six_sites_ok(tmp_path)
            chemins["quote_engine_photos"].write_text(
                '_MODES = ("residentiel", "industriel")\n', encoding="utf-8")
            trouves = guard.constats(set(QUATRE_MODES), chemins)
            self.assertEqual([site for site, _ in trouves], ["quote_engine_photos"])

    def test_site_illisible_rougit_en_nommant_le_chemin(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            chemins = _six_sites_ok(tmp_path)
            chemins["classifieurs"] = tmp_path / "absent.py"
            trouves = guard.constats(set(QUATRE_MODES), chemins)
            self.assertEqual([site for site, _ in trouves], ["classifieurs"])
            self.assertIn("illisible", trouves[0][1])


class ContratTests(unittest.TestCase):
    def test_contrat_sans_cle_modes_leve(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "vide.json"
            p.write_text(json.dumps({}), encoding="utf-8")
            with self.assertRaises(ValueError):
                guard.charger_contrat(p)

    def test_contrat_reel_porte_les_quatre_modes_exacts(self):
        canonique = guard.charger_contrat(guard.CONTRAT)
        self.assertEqual(canonique, set(QUATRE_MODES))


class DepotReelTests(unittest.TestCase):
    """Le dépôt réel doit être VERT : les six sites existent et concordent."""

    def test_le_depot_reel_est_VERT(self):
        canonique = guard.charger_contrat(guard.CONTRAT)
        trouves = guard.constats(canonique, {})
        self.assertEqual(trouves, [], trouves)

    def test_main_rend_0_sur_le_depot_reel(self):
        self.assertEqual(guard.main([]), 0)

    def test_main_rend_1_sur_un_contrat_illisible(self):
        self.assertEqual(guard.main(["--contrat", "/chemin/qui/n/existe/pas.json"]), 1)


if __name__ == "__main__":
    unittest.main()
