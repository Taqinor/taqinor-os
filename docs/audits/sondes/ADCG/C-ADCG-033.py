"""Les étapes « garde CVE » de dependency-audit.yml sortent 0 quand la garde sort 1 (tee sans pipefail)."""
SONDE = {"constat": "C-ADCG-033", "sha": "ce4e5fc4f",
         "attendu": "les deux étapes rejouées avec une garde qui sort 1 rendent le code 0"}

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[4]
WF = RACINE / ".github/workflows/dependency-audit.yml"


def _shell(wf, job, step):
    """Shell effectif d'une étape `run:` (règles GitHub : step > job > workflow)."""
    s = step.get("shell") or ((job.get("defaults") or {}).get("run") or {}).get("shell") \
        or ((wf.get("defaults") or {}).get("run") or {}).get("shell")
    if s is None:
        return ["-e", "-c"]                                  # bash -e {0}
    if s == "bash":
        return ["--noprofile", "--norc", "-eo", "pipefail", "-c"]
    return None


def sonde(ctx=None):
    wf = yaml.safe_load(WF.read_text(encoding="utf-8"))
    job = wf["jobs"]["audit"]
    bash = shutil.which("bash")
    codes, portee = {}, {}
    for step in job["steps"]:
        nom = step.get("name", "")
        if not (nom.startswith("Garde HIGH/CRITICAL") or nom.startswith("npm audit")):
            continue
        args = _shell(wf, job, step)
        # la garde (avant le premier `|` de chaque ligne) est remplacée par une commande qui sort 1
        script = "\n".join(re.sub(r"^(\s*)[^|#\n]+\|", r"\1(exit 1) |", ligne) if "|" in ligne else ligne
                           for ligne in step["run"].splitlines())
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp) / (step.get("working-directory") or ".")
            cwd.mkdir(parents=True, exist_ok=True)
            r = subprocess.run([bash, *args, script], cwd=cwd, capture_output=True, text=True)
        codes[nom] = r.returncode
    # portée : manifestes présents dans le dépôt mais jamais audités par le workflow
    texte = WF.read_text(encoding="utf-8")
    manifestes = ["backend/fastapi_ia/requirements.txt", "apps/web/package-lock.json",
                  "apps/yanbow-web/package-lock.json"]
    for m in manifestes:
        if (RACINE / m).exists():
            portee[m] = (m in texte) or (os.path.dirname(m) in texte)
    avales = [n for n, c in codes.items() if c == 0]
    return {"repro": bool(codes) and len(avales) == len(codes),
            "observe": f"codes de sortie avec garde=1 : {codes} ; manifestes audités : {portee}"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
