"""Rejoue les deux chemins de deploy (commandes factices) : le backend est redémarré (code neuf servi) AVANT migrate, et un migrate en échec côté auto est rejoué à chaque cycle, redémarrage compris, sans autre trace que le journal."""
SONDE = {"constat": "C-ADCG-002", "sha": "ce4e5fc4f",
         "attendu": "restart django_core précède migrate (auto backend seul, auto frontend+backend, manuel) ; 2 cycles auto en échec = 2 restarts + 2 ECHEC, last_deployed_commit inchangé"}
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
    for s in ("bin", "repo", "state"):
        (b / s).mkdir(exist_ok=True)
    for n in ("git", "docker", "flock"):
        (b / "bin" / n).write_bytes(SHIM.encode())
    t = texte.replace("/opt/taqinor-os", px(b / "repo")).replace("/opt/autodeploy", px(b / "state"))
    (b / "s.sh").write_bytes(t.replace("\r\n", "\n").encode())
    r = subprocess.run([bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_", px(b / "bin"), px(b / "s.sh")],
                       env={**os.environ, "BANC": px(b), "NEW": NEW, **env}, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    return r.returncode, r.stdout + r.stderr

def ordre(texte, changes, head, cycles=1, fail=""):
    with tempfile.TemporaryDirectory() as d:
        b = pathlib.Path(d)
        (b / "HEAD").write_text(head); (b / "changes").write_text(changes)
        (b / "state").mkdir(); (b / "state" / "last_deployed_commit").write_text(OLD)
        for _ in range(cycles):
            jouer(texte, d, {"FAIL": fail})
        calls = (b / "calls.log").read_text(encoding="utf-8").splitlines()
        log = (b / "state" / "deploy.log").read_text(encoding="utf-8") if (b / "state" / "deploy.log").exists() else ""
        last = (b / "state" / "last_deployed_commit").read_text().strip()
    ir = next((i for i, c in enumerate(calls) if " restart django_core" in c), None)
    im = next((i for i, c in enumerate(calls) if "manage.py migrate" in c), None)
    return ir, im, sum(" restart django_core" in c for c in calls), log.count("ECHEC"), last

def sonde(ctx=None):
    auto = (RACINE / "scripts/auto-deploy.sh").read_text(encoding="utf-8")
    ps1 = (RACINE / "scripts/deploy-prod.ps1").read_text(encoding="utf-8")
    remote = "ZERO_DOWNTIME=0\n" + re.search(r"\$remote = @'\r?\n(.*?)\r?\n'@", ps1, re.S).group(1)
    back = "backend/django_core/apps/crm/models.py\nbackend/django_core/apps/crm/migrations/0999_x.py\n"
    a1 = ordre(auto, back, OLD)
    a2 = ordre(auto, "frontend/src/App.jsx\n" + back, OLD)
    m1 = ordre(remote, back, OLD)
    boucle = ordre(auto, back, OLD, cycles=2, fail="manage.py migrate")
    avant = lambda o: o[0] is not None and o[1] is not None and o[0] < o[1]
    repro = avant(a1) and avant(a2) and avant(m1) and boucle[2] == 2 and boucle[3] == 2 and boucle[4] == OLD
    return {"repro": repro, "observe": (
        f"index(restart django_core) < index(migrate) : auto backend seul={avant(a1)} {a1[:2]}, "
        f"auto frontend+backend={avant(a2)} {a2[:2]}, manuel={avant(m1)} {m1[:2]} ; "
        f"2 cycles auto avec migrate en échec : restarts={boucle[2]}, ECHEC au journal={boucle[3]}, "
        f"last_deployed_commit={'OLD (inchangé)' if boucle[4] == OLD else boucle[4][:7]}")}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
