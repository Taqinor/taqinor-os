"""ADCG62 — les gardes CVE de `.github/workflows/dependency-audit.yml` bloquent.

Chaque étape « Garde HIGH/CRITICAL (backend) » et « npm audit » est rejouée
sous le shell EFFECTIF de GitHub (`bash -e {0}` sans `shell:`), la garde
remplacée par `(exit 1)` : l'étape doit sortir non nul. Sans `pipefail`, le
code de `tee` (0) masquait celui de la garde (C-ADCG-033, patron : la sonde).
    python -m unittest scripts.tests.test_dependency_audit_workflow -v
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows" / "dependency-audit.yml"
ETAPES = ("Garde HIGH/CRITICAL (backend)", "npm audit")


def _bash() -> str | None:
    if sys.platform == "win32":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        return str(git_bash) if git_bash.is_file() else None
    return shutil.which("bash")


def _args_shell(wf: dict, job: dict, step: dict) -> list[str]:
    """Shell effectif d'une étape `run:` (règles GitHub : step > job > workflow)."""
    shell = step.get("shell") or ((job.get("defaults") or {}).get("run") or {}).get("shell") \
        or ((wf.get("defaults") or {}).get("run") or {}).get("shell")
    if shell is None:
        return ["-e", "-c"]
    if shell == "bash":
        return ["--noprofile", "--norc", "-eo", "pipefail", "-c"]
    raise AssertionError(f"shell inattendu : {shell}")


def _garde_qui_sort_1(run: str) -> str:
    return "\n".join(re.sub(r"^(\s*)[^|#\n]+\|", r"\1(exit 1) |", ligne) if "|" in ligne else ligne
                     for ligne in run.splitlines())


@unittest.skipUnless(_bash(), "bash introuvable")
class GardesBloquantesTests(unittest.TestCase):
    def _etapes(self):
        wf = yaml.safe_load(WF.read_text(encoding="utf-8"))
        job = wf["jobs"]["audit"]
        etapes = [s for s in job["steps"] if str(s.get("name", "")).startswith(ETAPES)]
        self.assertEqual(len(etapes), 2, [s.get("name") for s in job["steps"]])
        return wf, job, etapes

    def test_garde_qui_sort_1_fait_echouer_l_etape(self):
        wf, job, etapes = self._etapes()
        for step in etapes:
            with self.subTest(etape=step["name"]), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp) / (step.get("working-directory") or ".")
                cwd.mkdir(parents=True, exist_ok=True)
                script = _garde_qui_sort_1(step["run"])
                self.assertIn("(exit 1) |", script)
                res = subprocess.run([_bash(), *_args_shell(wf, job, step), script],
                                     cwd=cwd, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(res.returncode, 0, f"étape avalée : {step['run']!r}")

    def test_garde_qui_sort_0_laisse_l_etape_verte(self):
        wf, job, etapes = self._etapes()
        for step in etapes:
            with self.subTest(etape=step["name"]), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp) / (step.get("working-directory") or ".")
                cwd.mkdir(parents=True, exist_ok=True)
                script = _garde_qui_sort_1(step["run"]).replace("(exit 1) |", "(exit 0) |")
                res = subprocess.run([_bash(), *_args_shell(wf, job, step), script],
                                     cwd=cwd, capture_output=True, text=True, timeout=30)
                self.assertEqual(res.returncode, 0, res.stderr)


if __name__ == "__main__":
    unittest.main()
