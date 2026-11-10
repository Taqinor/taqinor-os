"""ADCG96 — `scripts/serveur/installer-serveur.sh` rejoué au BANC : racine système
temporaire (RACINE), faux `systemctl` qui journalise ses appels. Aucun serveur.

Run : python -m unittest scripts.tests.test_installer_serveur -v
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.tests import test_auto_deploy as banc_deploy  # _bash, _px partagés

ROOT = Path(__file__).resolve().parents[2]
SERVEUR = ROOT / "scripts" / "serveur"
INSTALLER = SERVEUR / "installer-serveur.sh"
FAUX_SYSTEMCTL = '#!/usr/bin/env bash\necho "systemctl $*" >> "$BANC/calls.log"\n'


@unittest.skipUnless(banc_deploy._bash(), "bash introuvable")
class InstallerServeurTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)
        (self.d / "bin").mkdir()
        shim = self.d / "bin" / "systemctl"
        shim.write_text(FAUX_SYSTEMCTL, encoding="utf-8")
        shim.chmod(0o755)
        self.racine = self.d / "racine"

    def installer(self):
        px = banc_deploy._px
        r = subprocess.run(
            [banc_deploy._bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_",
             px(self.d / "bin"), px(INSTALLER)],
            env={**os.environ, "BANC": px(self.d), "RACINE": px(self.racine)},
            capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return (self.d / "calls.log").read_text(encoding="utf-8").splitlines()

    def etat(self):
        return {str(p.relative_to(self.racine)): p.read_bytes()
                for p in sorted(self.racine.rglob("*")) if p.is_file()}

    def test_installe_unites_et_active_le_timer(self):
        appels = self.installer()
        unites = self.racine / "etc" / "systemd" / "system"
        for nom in ("taqinor-autodeploy.service", "taqinor-autodeploy.timer"):
            self.assertEqual((unites / nom).read_bytes(), (SERVEUR / nom).read_bytes(), nom)
        script = self.racine / "opt" / "autodeploy" / "auto-deploy.sh"
        self.assertEqual(script.read_bytes(), (ROOT / "scripts" / "auto-deploy.sh").read_bytes())
        if os.name == "posix":
            self.assertTrue(os.access(script, os.X_OK))
        self.assertEqual(appels, ["systemctl daemon-reload",
                                  "systemctl enable taqinor-autodeploy.timer"])

    def test_installation_ne_demarre_pas_le_timer(self):
        # ADCG102 — le timer n'est démarré qu'en dernière étape de la procédure,
        # après last_deployed_commit et les contrôles (sinon deploy complet concurrent).
        for _passage in range(2):
            appels = self.installer()
            self.assertFalse([a for a in appels if " start" in a or "--now" in a], appels)
        doc = (ROOT / "docs" / "production.md").read_text(encoding="utf-8")
        section = doc.split("## Reconstruire le serveur", 1)[1].split("\n## ", 1)[0]
        demarrage = "systemctl start taqinor-autodeploy.timer"
        self.assertEqual(section.count(demarrage), 1)
        self.assertGreater(section.index(demarrage), section.index("last_deployed_commit"))
        self.assertGreater(section.index(demarrage), section.index("showmigrations"))

    def test_second_passage_idempotent(self):
        self.installer()
        avant = self.etat()
        appels = self.installer()
        self.assertEqual(self.etat(), avant)
        self.assertEqual(appels[2:], appels[:2])

    def test_unites_portent_les_reglages_de_prod(self):
        service = (SERVEUR / "taqinor-autodeploy.service").read_text(encoding="utf-8")
        timer = (SERVEUR / "taqinor-autodeploy.timer").read_text(encoding="utf-8")
        for ligne in ("Type=oneshot", "ExecStart=/opt/autodeploy/auto-deploy.sh"):
            self.assertIn(ligne, service.splitlines())
        for ligne in ("OnBootSec=2min", "OnUnitActiveSec=1min", "WantedBy=timers.target"):
            self.assertIn(ligne, timer.splitlines())


if __name__ == "__main__":
    unittest.main()
