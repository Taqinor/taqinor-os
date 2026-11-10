"""Rejoue la construction sélective des deux chemins de deploy (commandes factices) sur trois fichiers qui entrent dans une image ou un conteneur : apps/web/worker (image frontend), backend/minio (image minio), backend/db/postgresql.conf (conf montée de db) — aucun ne reconstruit ni ne redémarre son service."""
SONDE = {"constat": "C-ADCG-009", "sha": "ce4e5fc4f",
         "attendu": "pour chacun des 3 fichiers, auto et manuel : aucun `build` du service, aucun restart de db/minio, alors que Dockerfile.prod copie apps/web/worker et que compose construit minio et monte postgresql.conf"}
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
 *"python -c"*health*) echo ok;;
esac
exit 0
'''
CAS = {"apps/web/worker/deadLetter.mjs": "frontend", "backend/minio/Dockerfile": "minio",
       "backend/db/postgresql.conf": "db"}

def px(p):
    p = str(p).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:", p) else p

def bash():
    g = r"C:\Program Files\Git\bin\bash.exe"
    return g if os.path.exists(g) else shutil.which("bash")

def jouer(texte, changes):
    with tempfile.TemporaryDirectory() as d:
        b = pathlib.Path(d)
        for s in ("bin", "repo", "state"):
            (b / s).mkdir()
        for n in ("git", "docker", "flock"):
            (b / "bin" / n).write_bytes(SHIM.encode())
        (b / "HEAD").write_text(OLD); (b / "changes").write_text(changes)
        (b / "state" / "last_deployed_commit").write_text(OLD)
        t = texte.replace("/opt/taqinor-os", px(b / "repo")).replace("/opt/autodeploy", px(b / "state"))
        (b / "s.sh").write_bytes(t.replace("\r\n", "\n").encode())
        subprocess.run([bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_", px(b / "bin"), px(b / "s.sh")],
                       env={**os.environ, "BANC": px(b), "COMMIT_NEUF": NEW}, capture_output=True, timeout=120)
        return (b / "calls.log").read_text(encoding="utf-8").splitlines()

def sonde(ctx=None):
    auto = (RACINE / "scripts/auto-deploy.sh").read_text(encoding="utf-8")
    ps1 = (RACINE / "scripts/deploy-prod.ps1").read_text(encoding="utf-8")
    remote = "ZERO_DOWNTIME=0\n" + re.search(r"\$remote = @'\r?\n(.*?)\r?\n'@", ps1, re.S).group(1)
    dockerfile = (RACINE / "frontend/Dockerfile.prod").read_text(encoding="utf-8")
    compose = (RACINE / "docker-compose.yml").read_text(encoding="utf-8")
    entre = {"frontend": "COPY apps/web/worker" in dockerfile, "minio": "build: ./backend/minio" in compose,
             "db": "./backend/db/postgresql.conf:/etc/postgresql/postgresql.conf" in compose}
    res, inertes = {}, 0
    for fichier, service in CAS.items():
        for nom, texte in (("auto", auto), ("manuel", remote)):
            calls = jouer(texte, fichier + "\n")
            build = any(re.search(rf" build( .*)? {service}\b| build$", c) for c in calls)
            restart = any(re.search(rf" restart\b.*\b{service}\b", c) for c in calls if "rollback" not in c)
            res[f"{fichier}/{nom}"] = {"build": build, "restart": restart}
            inertes += (not build and not restart)
    repro = all(entre.values()) and inertes == 2 * len(CAS)
    return {"repro": repro, "observe": f"fichier réellement embarqué={entre} ; rejeu={res} ; cas inertes={inertes}/{2 * len(CAS)}"}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
