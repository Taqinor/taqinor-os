"""L'alerte d'api-fuzz-full ne compte aucun constat NOUVEAU écrit par resume_markdown (grep '^  NOUVEAU' sur des puces)."""
SONDE = {"constat": "C-ADCG-034", "sha": "ce4e5fc4f",
         "attendu": "16 verdicts dont 1 à constat nouveau -> 'constats hors dette : 0' et regression=success"}

import importlib.util
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[4]
WF = RACINE / ".github/workflows/api-fuzz-full.yml"
SCOPE = RACINE / "scripts/fuzz/api_fuzz_scope.py"


def sonde(ctx=None):
    spec = importlib.util.spec_from_file_location("api_fuzz_scope_sonde", SCOPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    nouveau = "Resource is not available after creation|Stateful tests"
    corps_rouge = mod.resume_markdown([nouveau], [])
    corps_vert = mod.resume_markdown([], [])
    wf = yaml.safe_load(WF.read_text(encoding="utf-8"))
    etape = next(s for s in wf["jobs"]["alerte"]["steps"] if s.get("id") == "verdict")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i in range(16):  # 16 tranches, toutes avec un verdict ; la 0 porte 1 constat nouveau
            d = tmp / "rapports" / f"schemathesis-report-{i}"
            d.mkdir(parents=True)
            (d / f"verdict-{i}.md").write_text(corps_rouge if i == 0 else corps_vert, encoding="utf-8")
        sortie, resume = tmp / "out.txt", tmp / "summary.md"
        sortie.touch()
        resume.touch()
        env = dict(os.environ, RUNNER_TEMP=str(tmp), GITHUB_OUTPUT=str(sortie),
                   GITHUB_STEP_SUMMARY=str(resume))
        r = subprocess.run([shutil.which("bash"), "--noprofile", "--norc", "-eo", "pipefail",
                            "-c", etape["run"]], cwd=tmp, env=env, capture_output=True, text=True)
        out = sortie.read_text(encoding="utf-8")
    ligne = next((l for l in r.stdout.splitlines() if l.startswith("Tranches :")), r.stdout.strip())
    return {"repro": "regression=success" in out,
            "observe": f"verdict écrit : {corps_rouge.splitlines()[-1]!r} ; étape : {ligne!r} ; "
                       f"GITHUB_OUTPUT : {out.strip()!r} (code {r.returncode})"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
