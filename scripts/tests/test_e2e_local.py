"""ADCG23 — `scripts/e2e-local.sh stop` n'arrête que les services que `up` a démarrés.

Un FAUX `docker` (en tête du PATH) journalise ses appels ; l'état du script vit
dans un dossier jetable (`E2E_ETAT_DIR`), jamais dans le /tmp du poste.
    python -m unittest scripts.tests.test_e2e_local -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "e2e-local.sh"

FAUX_DOCKER = '#!/bin/bash\necho "$*" >> "$FAUX_DOCKER_JOURNAL"\nexit 0\n'


def _bash() -> str | None:
    if sys.platform == "win32":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        return str(git_bash) if git_bash.is_file() else None
    return shutil.which("bash")


@unittest.skipUnless(_bash(), "bash introuvable")
class E2eLocalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        faux = self.tmp / "bin" / "docker"
        faux.write_text(FAUX_DOCKER, encoding="utf-8", newline="\n")
        faux.chmod(0o755)
        self.journal = self.tmp / "journal.txt"
        self.etat = self.tmp / "etat"
        self.etat.mkdir()

    def _stop(self):
        env = dict(os.environ, E2E_ETAT_DIR=self.etat.as_posix(),
                   FAUX_DOCKER_JOURNAL=self.journal.as_posix())
        env["PATH"] = str(self.tmp / "bin") + os.pathsep + env.get("PATH", "")
        res = subprocess.run([_bash(), SCRIPT.as_posix(), "stop"], capture_output=True, text=True,
                             encoding="utf-8", env=env, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        appels = self.journal.read_text(encoding="utf-8").splitlines() if self.journal.exists() else []
        return res.stdout, [a for a in appels if a.startswith("compose stop")]

    def test_stop_ne_coupe_que_ce_que_up_a_demarre(self):
        (self.etat / "taqinor-e2e-services.txt").write_text("minio\n", encoding="utf-8", newline="\n")
        _, arrets = self._stop()
        self.assertEqual(arrets, ["compose stop minio"])
        self.assertFalse((self.etat / "taqinor-e2e-services.txt").exists(), "état non effacé après stop")

    def test_sans_etat_rien_n_est_arrete(self):
        sortie, arrets = self._stop()
        self.assertEqual(arrets, [])
        self.assertIn("services laissés en marche (non démarrés par up)", sortie)

    def test_up_ne_retient_que_les_services_absents(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        releve = texte.index("docker compose ps --services --status running")
        self.assertLess(releve, texte.index("docker compose up -d db redis minio"))
        self.assertNotIn("docker compose stop db redis minio", texte)


if __name__ == "__main__":
    unittest.main()
