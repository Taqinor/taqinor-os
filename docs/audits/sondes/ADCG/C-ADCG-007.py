"""Rejoue auto-deploy.sh (commandes factices) avec un `caddy reload` refusé (Caddyfile invalide) : le deploy est annoncé OK, et aucun workflow CI ni script de deploy ne valide la configuration du proxy."""
SONDE = {"constat": "C-ADCG-007", "sha": "ce4e5fc4f",
         "attendu": "caddy reload en échec -> « DEPLOY … — OK » + commit marqué déployé ; 0 occurrence de caddy validate/adapt ou nginx -t dans .github/workflows et les scripts de deploy"}
import os, re, shutil, subprocess, tempfile, pathlib
RACINE = pathlib.Path(__file__).resolve().parents[4]
OLD, NEW = "a" * 40, "b" * 40
SHIM = r'''#!/usr/bin/env bash
n=$(basename "$0"); a="$n $*"; echo "$a" >> "$BANC/calls.log"
case "$a" in
 "git rev-parse origin/main") echo "$COMMIT_NEUF";;
 "git rev-parse --short "*) echo "${3:0:9}";;
 "git diff --name-only"*) cat "$BANC/changes";;
esac
if echo "$a" | grep -q "caddy reload"; then echo "Error: adapting config using caddyfile: unrecognized directive" >&2; exit 1; fi
exit 0
'''

def px(p):
    p = str(p).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:", p) else p

def bash():
    g = r"C:\Program Files\Git\bin\bash.exe"
    return g if os.path.exists(g) else shutil.which("bash")

def sonde(ctx=None):
    auto = (RACINE / "scripts/auto-deploy.sh").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as d:
        b = pathlib.Path(d)
        for s in ("bin", "repo", "state"):
            (b / s).mkdir()
        for n in ("git", "docker", "flock"):
            (b / "bin" / n).write_bytes(SHIM.encode())
        (b / "changes").write_text("backend/caddy/Caddyfile\n"); (b / "state" / "last_deployed_commit").write_text(OLD)
        t = auto.replace("/opt/taqinor-os", px(b / "repo")).replace("/opt/autodeploy", px(b / "state"))
        (b / "s.sh").write_bytes(t.replace("\r\n", "\n").encode())
        r = subprocess.run([bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_", px(b / "bin"), px(b / "s.sh")],
                           env={**os.environ, "BANC": px(b), "COMMIT_NEUF": NEW}, capture_output=True, timeout=120)
        log = (b / "state" / "deploy.log").read_text(encoding="utf-8")
        calls = (b / "calls.log").read_text(encoding="utf-8")
        last = (b / "state" / "last_deployed_commit").read_text().strip()
    reload_tente = "caddy reload" in calls
    annonce_ok = bool(re.search(r"DEPLOY \w+ — OK", log))
    motif = re.compile(r"caddy (validate|adapt)|nginx -t\b|nginx\s+-t\b")
    surfaces = list((RACINE / ".github/workflows").glob("*.y*ml")) + [RACINE / "scripts/auto-deploy.sh", RACINE / "scripts/deploy-prod.ps1"]
    validations = [str(p.relative_to(RACINE)) for p in surfaces if motif.search(p.read_text(encoding="utf-8", errors="replace"))]
    repro = r.returncode == 0 and reload_tente and annonce_ok and last == NEW and not validations
    return {"repro": repro, "observe": (
        f"Caddyfile modifié + reload refusé : rc={r.returncode}, reload tenté={reload_tente}, journal OK={annonce_ok}, "
        f"commit marqué déployé={last == NEW} ; fichiers CI/deploy qui valident la conf proxy : {validations or 'aucun'}")}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
