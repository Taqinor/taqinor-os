"""ADCG21 — scripts/gc-workspace.ps1 exécuté sur un dépôt git temporaire (en -WhatIf).

Le script se résout par `$PSScriptRoot` : on le copie sous `scripts/` du dépôt de test.
Run:
    python -m unittest scripts.tests.test_gc_workspace -v
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "gc-workspace.ps1"
PWSH = shutil.which("pwsh") or shutil.which("powershell")


def _git(depot, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=depot, capture_output=True, text=True, check=True,
    ).stdout


@unittest.skipUnless(PWSH and shutil.which("git"), "pwsh/powershell ou git absent")
class GcWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.depot = Path(self._tmp.name)
        _git(self.depot, "init", "-q", "-b", "main")
        (self.depot / "a.txt").write_text("a\n", encoding="utf-8")
        _git(self.depot, "add", "a.txt")
        _git(self.depot, "commit", "-q", "-m", "a")
        _git(self.depot, "branch", "worktree-agent-x")
        _git(self.depot, "checkout", "-q", "-b", "worktree-agent-y")
        (self.depot / "b.txt").write_text("b\n", encoding="utf-8")
        _git(self.depot, "add", "b.txt")
        _git(self.depot, "commit", "-q", "-m", "b")
        _git(self.depot, "checkout", "-q", "main")
        (self.depot / "scripts").mkdir()
        shutil.copy(SCRIPT, self.depot / "scripts" / "gc-workspace.ps1")

    def tearDown(self):
        self._tmp.cleanup()

    def _lancer(self, *extra):
        r = subprocess.run(
            [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(self.depot / "scripts" / "gc-workspace.ps1"), "-WhatIf", *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_branche_worktree_agent_fusionnee_supprimee(self):
        sortie = self._lancer()
        self.assertIn("delete merged branch worktree-agent-x", sortie)
        self.assertNotIn("delete merged branch worktree-agent-y", sortie)
        garde = sortie[sortie.index("KEEP (non fusionn"):]
        self.assertIn("- worktree-agent-y", garde)
        branches = _git(self.depot, "branch", "--format=%(refname:short)").split()
        self.assertEqual(sorted(branches), ["main", "worktree-agent-x", "worktree-agent-y"])


if __name__ == "__main__":
    unittest.main()
