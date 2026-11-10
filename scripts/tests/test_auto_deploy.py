"""ADCG1+ — la séquence de deploy (`scripts/auto-deploy.sh`) et son déclencheur
manuel (`scripts/deploy-prod.ps1`) rejoués au BANC : faux `git` / `docker` /
`flock` / `systemctl` / `curl` qui journalisent chaque appel dans `calls.log`,
arborescence /opt remplacée par un dossier temporaire. Aucun serveur, aucun
docker réel. Patron : `docs/audits/sondes/ADCG/C-ADCG-002.py`.

Run : python -m unittest scripts.tests.test_auto_deploy -v
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTO = ROOT / "scripts" / "auto-deploy.sh"
PS1 = ROOT / "scripts" / "deploy-prod.ps1"
A, B, C = "a" * 40, "b" * 40, "c" * 40

# Faux exécutable commun : journalise « <nom> <args> », simule quelques sorties,
# et sort en 1 quand l'appel correspond au motif FAIL (regex étendue).
SHIM = r'''#!/usr/bin/env bash
n=$(basename "$0"); a="$n $*"; echo "$a" >> "$BANC/calls.log"
case "$a" in
 "git rev-parse origin/main") cat "$BANC/origin";;
 "git rev-parse HEAD") cat "$BANC/HEAD";;
 "git rev-parse --short "*) echo "${3:0:9}";;
 "git diff --name-only"*) cat "$BANC/changes";;
 "git reset --hard "*) t=$3; [ "$t" = origin/main ] && t=$(cat "$BANC/origin"); echo "$t" > "$BANC/HEAD";;
 "git show origin/main:scripts/auto-deploy.sh") cat "$BANC/auto_origin.sh";;
 *"python -c"*health*) echo "${HEALTH-ok}";;
 *showmigrations*) printf '%b' "${SHOWMIG-}";;
esac
if [ -n "${FAIL:-}" ] && echo "$a" | grep -qE "$FAIL"; then exit 1; fi
exit 0
'''
SHIMS = ("git", "docker", "flock", "systemctl", "curl")


def _px(chemin):
    """Chemin vu par bash (Git Bash sous Windows : /c/...)."""
    p = str(chemin).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:", p) else p


def _bash():
    git_bash = r"C:\Program Files\Git\bin\bash.exe"
    return git_bash if os.path.exists(git_bash) else shutil.which("bash")


def _remote():
    """Le script distant de deploy-prod.ps1 (here-string `$remote`)."""
    texte = PS1.read_text(encoding="utf-8")
    corps = re.search(r"\$remote = @'\r?\n(.*?)\r?\n'@", texte, re.S).group(1)
    return "ZERO_DOWNTIME=0\n" + corps


class Banc:
    """Racine système factice : bin/ (faux exécutables), repo/, state/."""

    def __init__(self, dossier, changes="", last=A, origin=B):
        self.d = Path(dossier)
        for sous in ("bin", "repo/backend/db", "state"):
            (self.d / sous).mkdir(parents=True, exist_ok=True)
        for nom in SHIMS:
            shim = self.d / "bin" / nom
            shim.write_bytes(SHIM.encode())
            shim.chmod(0o755)
        (self.d / "repo/backend/db/provision_sql_agent_ro.sh").write_bytes(
            b'echo PROVISION >> "$BANC/calls.log"\n')
        (self.d / "HEAD").write_text(last or A)
        (self.d / "origin").write_text(origin)
        (self.d / "changes").write_text(changes)
        (self.d / "auto_origin.sh").write_bytes(AUTO.read_bytes())
        if last:
            self.ecrire("last_deployed_commit", last)

    def ecrire(self, nom, valeur):
        (self.d / "state" / nom).write_text(valeur)

    def lire(self, nom):
        f = self.d / "state" / nom
        return f.read_text(encoding="utf-8").strip() if f.exists() else None

    def jouer(self, texte=None, **env):
        texte = AUTO.read_text(encoding="utf-8") if texte is None else texte
        texte = (texte.replace("/opt/taqinor-os", _px(self.d / "repo"))
                 .replace("/opt/autodeploy", _px(self.d / "state")))
        script = self.d / "s.sh"
        script.write_bytes(texte.replace("\r\n", "\n").encode())
        r = subprocess.run(
            [_bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_",
             _px(self.d / "bin"), _px(script)],
            env={**os.environ, "BANC": _px(self.d), **env}, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=180)
        return r.returncode, r.stdout + r.stderr

    @property
    def appels(self):
        f = self.d / "calls.log"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    @property
    def journal(self):
        return self.lire("deploy.log") or ""

    def index(self, motif):
        return next((i for i, a in enumerate(self.appels) if re.search(motif, a)), None)

    def compte(self, motif):
        return sum(1 for a in self.appels if re.search(motif, a))


LOT_ECRAN_API = "frontend/src/pages/ventes/Liste.jsx\nbackend/django_core/apps/ventes/views.py\n"


@unittest.skipUnless(_bash(), "bash introuvable")
class AutoDeployTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def banc(self, **kw):
        return Banc(self._tmp.name, **kw)

    def test_manuel_declenche_la_sequence_unique(self):
        banc = self.banc(changes=LOT_ECRAN_API)
        rc, sortie = banc.jouer(_remote())
        self.assertEqual(rc, 0, sortie)
        commandes = {a.split(" ")[0] + " " + a.split(" ")[1] for a in banc.appels}
        self.assertEqual(commandes, {"git fetch", "git show", "systemctl start"}, banc.appels)
        self.assertIn("systemctl start taqinor-autodeploy.service", banc.appels)
        self.assertNotIn("docker compose", _remote())
        self.assertNotIn("manage.py", _remote())
        self.assertEqual((banc.d / "state" / "auto-deploy.sh").read_bytes(), AUTO.read_bytes())
        # Le code de sortie de la séquence est rendu tel quel.
        (banc.d / "calls.log").unlink()
        rc, _ = banc.jouer(_remote(), FAIL="^systemctl start")
        self.assertNotEqual(rc, 0)
        # La séquence unique : écran + API -> build frontend, restart backend, six étapes.
        (banc.d / "calls.log").unlink()
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie + banc.journal)
        self.assertIsNotNone(banc.index(r"prod\.yml build frontend$"))
        self.assertIsNotNone(banc.index(r" restart django_core "))
        for motif in ("PROVISION", "seed_catalogue", "pg_isready", "showmigrations",
                      r"ps -a --format", "builder prune"):
            self.assertIsNotNone(banc.index(motif), motif)
        self.assertEqual(banc.lire("last_deployed_commit"), B)
        self.assertIn("— OK", banc.journal)

    def test_zero_downtime_drapeau_lu_puis_efface(self):
        banc = self.banc(changes=LOT_ECRAN_API)
        rc, _ = banc.jouer(_remote().replace("ZERO_DOWNTIME=0", "ZERO_DOWNTIME=1"))
        self.assertEqual(rc, 0)
        self.assertIsNotNone(banc.lire("zero_downtime"))
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie)
        self.assertIsNotNone(banc.index(r"--scale django_core=2"))
        self.assertIsNone(banc.lire("zero_downtime"))


if __name__ == "__main__":
    unittest.main()
