"""ADEP27 - un depot range sous un dossier nomme `build/`, `dist/` ou `parked/`
doit donner le MEME verdict : les filtres de dossiers des gardes portent sur
le chemin RELATIF a la racine du depot, jamais sur le chemin absolu.

Pour chaque garde : on copie `scripts/*.py` (la garde et ses voisins importes)
+ `STAGES.py` + un arbre jouet sous `tmp/repo` puis sous `tmp/<dossier>/repo`,
on lance la garde dans chacun et on exige le meme code de sortie.
Stdlib pure.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

GARDES = (
    "check_stages.py",
    "check_test_determinism.py",
    "check_test_tenant_distinctness.py",
    "check_api_contract.py",
    "check_openapi_shapes.py",
    "check_parked_apps.py",
    "check_odoo_writes.py",
    "check_ecrans_atteignables.py",
    "check_ip_primitive.py",
    "check_liste_page1.py",
)
DOSSIERS_PIEGES = ("build", "dist", "parked")

ARBRE_JOUET = {
    # check_stages : deux violations (affectation litterale + liste de stages)
    "backend/x/bad.py": "lead.stage = 'SIGNED'\nPIPELINE_STAGES = ['NEW', 'FOO']\n",
    # check_test_determinism : un sleep dans un test
    "backend/django_core/apps/x/tests/test_t.py":
        "import time\n\n\ndef test_a():\n    time.sleep(1)\n",
    "backend/django_core/apps/x/__init__.py": "",
    "frontend/src/features/x/Liste.jsx":
        "export default function Liste() {\n"
        "  const charger = () => api.get('/x/').then((r) => setRows(r.data.results))\n"
        "  return null\n}\n",
}


def _monter(base: Path) -> Path:
    repo = base / "repo"
    (repo / "scripts").mkdir(parents=True)
    for source in (ROOT / "scripts").glob("*.py"):
        shutil.copy(source, repo / "scripts" / source.name)
    shutil.copy(ROOT / "STAGES.py", repo / "STAGES.py")
    parked = ROOT / "backend" / "django_core" / "core" / "parked.py"
    cible = repo / "backend" / "django_core" / "core" / "parked.py"
    cible.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(parked, cible)
    for rel, contenu in ARBRE_JOUET.items():
        chemin = repo / rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")
    return repo


def _lancer(repo: Path, garde: str) -> int:
    resultat = subprocess.run(
        [sys.executable, f"scripts/{garde}"], cwd=repo, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=300)
    return resultat.returncode


class GardesDepotDeplaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.plat = _monter(base / "plat")
        cls.deplaces = {d: _monter(base / d) for d in DOSSIERS_PIEGES}
        cls.verdicts = {g: _lancer(cls.plat, g) for g in GARDES}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_arbre_jouet_viole_check_stages(self):
        self.assertEqual(self.verdicts["check_stages.py"], 1)

    def test_meme_arbre_meme_verdict_sous_un_dossier_piege(self):
        for dossier, repo in self.deplaces.items():
            for garde in GARDES:
                with self.subTest(dossier=dossier, garde=garde):
                    self.assertEqual(_lancer(repo, garde), self.verdicts[garde],
                                     f"{garde} change de verdict sous {dossier}/")


if __name__ == "__main__":
    unittest.main()
