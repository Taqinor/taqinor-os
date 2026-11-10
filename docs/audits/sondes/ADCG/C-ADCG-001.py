"""Rejoue auto-deploy.sh puis le script distant de deploy-prod.ps1 (commandes factices) : migrate en échec -> l'auto ne revient pas en arrière, et le « rollback » manuel vise le commit fautif."""
SONDE = {"constat": "C-ADCG-001", "sha": "ce4e5fc4f",
         "attendu": "auto : ECHEC sans aucun git reset vers l'ancien commit ; manuel lancé après : PREV_SHA = commit fautif ; jamais d'écriture de last_deployed_commit"}
import os, re, shutil, subprocess, tempfile, pathlib
RACINE = pathlib.Path(__file__).resolve().parents[4]
OLD, NEW = "a" * 40, "b" * 40
SHIM = r'''#!/usr/bin/env bash
n=$(basename "$0"); a="$n $*"; echo "$a" >> "$BANC/calls.log"
case "$a" in
 "git rev-parse origin/main") echo "$COMMIT_NEUF";;
 "git rev-parse HEAD") cat "$BANC/HEAD";;
 "git rev-parse --short "*) echo "${3:0:9}";;
 "git diff --name-only"*) cat "$BANC/changes";;
 "git reset --hard "*) t=$3; [ "$t" = origin/main ] && t=$COMMIT_NEUF; echo "$t" > "$BANC/HEAD";;
 *"python -c"*health*) echo "${HEALTH-ok}";;
esac
if [ -n "${FAIL:-}" ] && echo "$a" | grep -qE "$FAIL"; then exit 1; fi
exit 0
'''

def px(p):
    p = str(p).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:", p) else p

def bash():
    g = r"C:\Program Files\Git\bin\bash.exe"
    return g if os.path.exists(g) else shutil.which("bash")

def jouer(texte, banc, env):
    b = pathlib.Path(banc)
    (b / "bin").mkdir(exist_ok=True); (b / "repo").mkdir(exist_ok=True); (b / "state").mkdir(exist_ok=True)
    for n in ("git", "docker", "flock"):
        (b / "bin" / n).write_bytes(SHIM.encode())
    t = texte.replace("/opt/taqinor-os", px(b / "repo")).replace("/opt/autodeploy", px(b / "state"))
    (b / "s.sh").write_bytes(t.replace("\r\n", "\n").encode())
    r = subprocess.run([bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_", px(b / "bin"), px(b / "s.sh")],
                       env={**os.environ, "BANC": px(b), "COMMIT_NEUF": NEW, **env}, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    return r.returncode, r.stdout + r.stderr

def sonde(ctx=None):
    auto = (RACINE / "scripts/auto-deploy.sh").read_text(encoding="utf-8")
    ps1 = (RACINE / "scripts/deploy-prod.ps1").read_text(encoding="utf-8")
    remote = "ZERO_DOWNTIME=0\n" + re.search(r"\$remote = @'\r?\n(.*?)\r?\n'@", ps1, re.S).group(1)
    with tempfile.TemporaryDirectory() as d:
        b = pathlib.Path(d)
        (b / "HEAD").write_text(OLD); (b / "changes").write_text("backend/django_core/apps/crm/views.py\n")
        (b / "state").mkdir(); (b / "state" / "last_deployed_commit").write_text(OLD)
        rc_a, _ = jouer(auto, d, {"FAIL": "manage.py migrate"})
        log = (b / "state" / "deploy.log").read_text(encoding="utf-8")
        calls = (b / "calls.log").read_text(encoding="utf-8")
        head_apres_auto = (b / "HEAD").read_text().strip()
        auto_revient = f"reset --hard {OLD}" in calls
        rc_m, out_m = jouer(remote, d, {"FAIL": "manage.py migrate"})
        m = re.search(r"Commit precedent \(rollback cible si besoin\): (\w+)", out_m)
        prev = m.group(1) if m else None
        head_final = (b / "HEAD").read_text().strip()
    ecrit_last = "last_deployed_commit" in remote
    repro = (rc_a != 0 and "ECHEC" in log and not auto_revient and head_apres_auto == NEW
             and prev == NEW and head_final == NEW and not ecrit_last)
    return {"repro": repro, "observe": (
        f"auto rc={rc_a}, ECHEC journalisé={'ECHEC' in log}, git reset vers l'ancien commit={auto_revient}, "
        f"HEAD après auto={'NEW (fautif)' if head_apres_auto == NEW else head_apres_auto[:7]} ; manuel rc={rc_m}, "
        f"PREV_SHA={'NEW (fautif)' if prev == NEW else prev}, HEAD après « ROLLBACK »={'NEW' if head_final == NEW else 'OLD'} ; "
        f"script distant écrit last_deployed_commit={ecrit_last}")}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
