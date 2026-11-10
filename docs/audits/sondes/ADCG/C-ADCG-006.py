"""Rejoue les DEUX copies de la séquence de deploy (auto-deploy.sh et le script distant de deploy-prod.ps1) sur le même lot frontend + backend : le manuel ne redémarre pas django, et l'auto saute six étapes du manuel."""
SONDE = {"constat": "C-ADCG-006", "sha": "ce4e5fc4f",
         "attendu": "lot frontend+backend : auto redémarre django_core, manuel non ; étapes du manuel absentes de l'auto non vides"}
import os, re, shutil, subprocess, tempfile, pathlib
RACINE = pathlib.Path(__file__).resolve().parents[4]
OLD, NEW = "a" * 40, "b" * 40
SHIM = r'''#!/usr/bin/env bash
n=$(basename "$0"); a="$n $*"; echo "$a" >> "$BANC/calls.log"
case "$a" in
 "git rev-parse origin/main") echo "$NEW";;
 "git rev-parse HEAD") cat "$BANC/HEAD";;
 "git rev-parse --short "*) echo "${3:0:9}";;
 "git diff --name-only"*) cat "$BANC/changes";;
 "git reset --hard "*) t=$3; [ "$t" = origin/main ] && t=$NEW; echo "$t" > "$BANC/HEAD";;
 *"python -c"*health*) echo ok;;
esac
exit 0
'''
ETAPES = {"provision_sql_agent_ro": "PROVISION", "seed_catalogue": "seed_catalogue", "wait_db": "pg_isready",
          "contrôle showmigrations": "showmigrations", "nettoyage conteneurs renommés": "ps -a --format",
          "prune": "builder prune"}

def px(p):
    p = str(p).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:", p) else p

def bash():
    g = r"C:\Program Files\Git\bin\bash.exe"
    return g if os.path.exists(g) else shutil.which("bash")

def jouer(texte, changes):
    with tempfile.TemporaryDirectory() as d:
        b = pathlib.Path(d)
        for s in ("bin", "repo/backend/db", "state"):
            (b / s).mkdir(parents=True)
        for n in ("git", "docker", "flock"):
            (b / "bin" / n).write_bytes(SHIM.encode())
        (b / "repo/backend/db/provision_sql_agent_ro.sh").write_bytes(b'echo PROVISION >> "$BANC/calls.log"\n')
        (b / "HEAD").write_text(OLD); (b / "changes").write_text(changes)
        (b / "state" / "last_deployed_commit").write_text(OLD)
        t = texte.replace("/opt/taqinor-os", px(b / "repo")).replace("/opt/autodeploy", px(b / "state"))
        (b / "s.sh").write_bytes(t.replace("\r\n", "\n").encode())
        r = subprocess.run([bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_", px(b / "bin"), px(b / "s.sh")],
                           env={**os.environ, "BANC": px(b), "NEW": NEW}, capture_output=True, timeout=120)
        return r.returncode, (b / "calls.log").read_text(encoding="utf-8")

def sonde(ctx=None):
    auto = (RACINE / "scripts/auto-deploy.sh").read_text(encoding="utf-8")
    ps1 = (RACINE / "scripts/deploy-prod.ps1").read_text(encoding="utf-8")
    remote = "ZERO_DOWNTIME=0\n" + re.search(r"\$remote = @'\r?\n(.*?)\r?\n'@", ps1, re.S).group(1)
    lot = "frontend/src/pages/ventes/Liste.jsx\nbackend/django_core/apps/ventes/views.py\n"
    rc_a, ca = jouer(auto, lot)
    rc_m, cm = jouer(remote, lot)
    auto_restart = " restart django_core" in ca
    man_restart = " restart django_core" in cm
    manquent = [nom for nom, motif in ETAPES.items() if motif in cm and motif not in ca]
    repro = rc_a == 0 and rc_m == 0 and auto_restart and not man_restart and bool(manquent)
    return {"repro": repro, "observe": (
        f"lot frontend+backend : rc auto={rc_a}, rc manuel={rc_m} ; build frontend auto={' build  frontend' in ca or 'build frontend' in ca}, "
        f"manuel={'build  frontend' in cm or 'build frontend' in cm} ; restart django_core auto={auto_restart}, manuel={man_restart} ; "
        f"étapes du manuel absentes de l'auto : {manquent}")}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
