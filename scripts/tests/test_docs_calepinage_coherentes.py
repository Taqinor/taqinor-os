"""Cohérence des docs du module Calepinage avec le code (ACAL333) — sans base de données."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACK = ROOT / "backend" / "django_core"
DOCS = ROOT / "docs"
EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".md", ".json", ".yml", ".mjs")


def _lire(chemin):
    return Path(chemin).read_text(encoding="utf-8")


class DocsCalepinageCoherentes(unittest.TestCase):
    def test_chaque_chemin_en_backticks_de_calepinage_module_existe(self):
        texte = _lire(DOCS / "calepinage-module.md")
        manquants = []
        for brut in re.findall(r"`([^`\n]+)`", texte):
            chemin = brut.split("::")[0].strip()
            if "/" not in chemin or " " in chemin or not chemin.endswith(EXTENSIONS):
                continue
            if any(c in chemin for c in "<>*{}$"):
                continue
            chemin = chemin.lstrip("./")
            racines = (ROOT, BACK, BACK / "apps", BACK / "apps" / "calepinage", ROOT / "frontend" / "src")
            if not any((r / chemin).exists() for r in racines):
                manquants.append(brut)
        self.assertEqual(manquants, [], "chemins cités par docs/calepinage-module.md absents du dépôt")

    def test_codemap_cite_le_nombre_reel_d_onglets_et_de_modeles(self):
        codemap = _lire(DOCS / "CODEMAP.md")
        modeles = _lire(BACK / "apps" / "calepinage" / "models.py")
        n_modeles = len(re.findall(r"^class \w+\(TenantModel\)", modeles, re.M))
        ligne = next(entree for entree in codemap.splitlines() if entree.startswith("| `calepinage` | `calepinage/` |"))
        self.assertEqual(int(ligne.split("|")[3]), n_modeles)
        onglets = _lire(ROOT / "frontend" / "src" / "features" / "calepinage" / "atelier" / "onglets.js")
        n_onglets = len(re.findall(r"\{ cle: '", onglets))
        self.assertIn("%d onglets du rail" % n_onglets, codemap)

    def test_aucune_reference_a_apps_ao_contract_samples_ni_ImportDxf(self):
        interdits = ("apps.ao", "apps/ao", "ImportDxf")
        for nom in ("calepinage-module.md", "moteur-calepinage.md"):
            texte = _lire(DOCS / nom)
            for mot in interdits:
                self.assertNotIn(mot, texte, "%s cite %s" % (nom, mot))
        guide = _lire(DOCS / "GUIDE_UTILISATEUR_ERP.md")
        debut = guide.index("### Calepinage")
        fin = guide.find(chr(10) + "### ", debut + 5)
        section = guide[debut:fin if fin != -1 else len(guide)]
        self.assertNotIn("Appel d'offres", section)
        readme = _lire(BACK / "apps" / "calepinage" / "contract_samples" / "README.md")
        self.assertNotIn("apps/ao/contract_samples", readme)


if __name__ == "__main__":
    unittest.main()
