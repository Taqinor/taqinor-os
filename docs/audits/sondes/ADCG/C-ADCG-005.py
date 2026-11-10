"""Rejoue auto-deploy.sh (commandes factices) sur la liste RÉELLE des fichiers des merges 65a889e1c (sentry-sdk) et fea43ee77 (Pillow) : un merge requirements.txt + docs est classé « docs seulement », aucune image n'est reconstruite et le commit est marqué déployé."""
SONDE = {"constat": "C-ADCG-005", "sha": "ce4e5fc4f",
         "attendu": "pour chaque merge : journal « docs/markdown uniquement », aucun `compose build`, last_deployed_commit = NEW"}
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
exit 0
'''
REPLI = {"65a889e1c": "backend/django_core/requirements.txt\ndocs/CODEMAP.md\n",
         "fea43ee77": "backend/django_core/requirements.txt\ndocs/CODEMAP.md\n"}

def px(p):
    p = str(p).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:", p) else p

def bash():
    g = r"C:\Program Files\Git\bin\bash.exe"
    return g if os.path.exists(g) else shutil.which("bash")

def fichiers(merge):
    r = subprocess.run(["git", "-C", str(RACINE), "diff", "--name-only", f"{merge}^1", merge],
                       capture_output=True, text=True)
    return (r.stdout if r.returncode == 0 and r.stdout.strip() else REPLI[merge]), r.returncode == 0

def jouer(texte, changes):
    with tempfile.TemporaryDirectory() as d:
        b = pathlib.Path(d)
        for s in ("bin", "repo", "state"):
            (b / s).mkdir()
        for n in ("git", "docker", "flock"):
            (b / "bin" / n).write_bytes(SHIM.encode())
        (b / "changes").write_text(changes); (b / "state" / "last_deployed_commit").write_text(OLD)
        t = texte.replace("/opt/taqinor-os", px(b / "repo")).replace("/opt/autodeploy", px(b / "state"))
        (b / "s.sh").write_bytes(t.replace("\r\n", "\n").encode())
        subprocess.run([bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_", px(b / "bin"), px(b / "s.sh")],
                       env={**os.environ, "BANC": px(b), "COMMIT_NEUF": NEW}, capture_output=True, timeout=120)
        log = (b / "state" / "deploy.log").read_text(encoding="utf-8")
        calls = (b / "calls.log").read_text(encoding="utf-8")
        last = (b / "state" / "last_deployed_commit").read_text().strip()
    return "docs/markdown uniquement" in log, " build" in calls, last == NEW

def sonde(ctx=None):
    auto = (RACINE / "scripts/auto-deploy.sh").read_text(encoding="utf-8")
    res, tous = {}, True
    for merge in REPLI:
        liste, du_git = fichiers(merge)
        docs, build, marque = jouer(auto, liste)
        res[merge] = {"fichiers": liste.split(), "lus_par_git": du_git, "classé_docs": docs,
                      "image_reconstruite": build, "marqué_déployé": marque}
        tous = tous and docs and not build and marque and "backend/django_core/requirements.txt" in liste
    seul, _, _ = jouer(auto, "backend/django_core/requirements.txt\n")
    return {"repro": tous and seul, "observe": f"{res} ; requirements.txt seul classé docs={seul}"}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
