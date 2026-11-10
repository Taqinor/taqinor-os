"""ADCG6 — le message final de `scripts/deploy-prod.ps1` suit le JOURNAL du serveur.

Le script est lancé par PowerShell (pwsh, présent sur les exécuteurs ubuntu ;
Windows PowerShell en repli sur un poste) avec `ssh` / `scp` remplacés par des
FONCTIONS PowerShell (résolues avant les exécutables) : aucune connexion réelle.

Run : python -m unittest scripts.tests.test_deploy_prod -v
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS1 = ROOT / "scripts" / "deploy-prod.ps1"

ENVELOPPE = r'''[Console]::OutputEncoding = [Text.Encoding]::UTF8
function scp { $global:LASTEXITCODE = 0 }
function ssh {
    foreach ($ligne in ($env:FAUX_SSH_SORTIE -split '\|')) { $ligne }
    $global:LASTEXITCODE = [int]$env:FAUX_SSH_RC
}
& '__PS1__'
exit $LASTEXITCODE
'''


def _powershell():
    return shutil.which("pwsh") or shutil.which("powershell")


class DeployProdTests(unittest.TestCase):
    def jouer(self, sortie, rc):
        shell = _powershell()
        self.assertTrue(shell, "pwsh introuvable : ce test ne se saute jamais")
        with tempfile.TemporaryDirectory() as d:
            enveloppe = Path(d) / "enveloppe.ps1"
            enveloppe.write_text(ENVELOPPE.replace("__PS1__", str(PS1)), encoding="utf-8-sig")
            r = subprocess.run(
                [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(enveloppe)],
                env={**os.environ, "FAUX_SSH_SORTIE": sortie, "FAUX_SSH_RC": str(rc),
                     "USERPROFILE": d}, capture_output=True, timeout=120)
        return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")

    def test_message_suit_le_journal_du_serveur(self):
        rc, sortie = self.jouer(
            "Deploiement lance|[2026-11-10T10:00:00Z] DEPLOY b4c5d6e — ECHEC (x)|"
            "[2026-11-10T10:01:00Z] ROLLBACK vers a1b2c3d effectué", 1)
        self.assertEqual(rc, 1, sortie)
        self.assertIn("ECHEC — retour arrière vers a1b2c3d effectué", sortie)

        rc, sortie = self.jouer("Deploiement lance|DEPLOY b4c5d6e — ECHEC", 1)
        self.assertEqual(rc, 1, sortie)
        self.assertIn("ECHEC SANS retour arrière : DEPLOY b4c5d6e — ECHEC", sortie)
        self.assertNotIn("retour arrière vers", sortie)
        self.assertNotIn("rollback automatique", sortie.lower())

        rc, sortie = self.jouer("Deploiement lance|DEPLOY b4c5d6e — OK", 0)
        self.assertEqual(rc, 0, sortie)
        self.assertIn("Deploiement termine", sortie)
        self.assertNotIn("sslip.io", PS1.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
