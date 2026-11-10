"""Rejoue le script distant de deploy-prod.ps1 (commandes factices) en faisant échouer une étape à la fois : la plupart des sorties non nulles ne restaurent rien, alors que l'enveloppe PowerShell annonce toujours « rollback automatique effectué »."""
SONDE = {"constat": "C-ADCG-003", "sha": "ce4e5fc4f",
         "attendu": "≥ 6 étapes en échec sortent non nul SANS rollback ni retour du code, et le bloc PowerShell affiche le message de rollback pour tout code non nul"}
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
 *showmigrations*) printf '%b' "${SHOWMIG-}";;
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
                       env={**os.environ, "BANC": px(b), "COMMIT_NEUF": NEW, **env}, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    return r.returncode, r.stdout + r.stderr

CAS = {  # étape en échec -> (motif FAIL, fichiers changés, sortie showmigrations)
    "verrou 45 min": ("^flock", "", ""),
    "build ciblé": (r"prod\.yml build", "backend/django_core/requirements.txt\n", ""),
    "up -d": (r"prod\.yml up -d --remove-orphans$", "", ""),
    "restart backend": ("restart django_core", "", ""),
    "UNAPPLIED≠0": ("", "", r"[X] a.0001\n[ ] a.0002\n"),
    "init_roles": ("init_roles", "", ""),
    "restart nginx": (r"prod\.yml restart nginx$", "", ""),
    "caddy reload": ("caddy reload", "", ""),
    "préchauffage": (r"django_core python$", "", ""),
}

def sonde(ctx=None):
    ps1 = (RACINE / "scripts/deploy-prod.ps1").read_text(encoding="utf-8")
    remote = "ZERO_DOWNTIME=0\n" + re.search(r"\$remote = @'\r?\n(.*?)\r?\n'@", ps1, re.S).group(1)
    sans_rollback = []
    for nom, (fail, changes, showmig) in CAS.items():
        with tempfile.TemporaryDirectory() as d:
            b = pathlib.Path(d)
            (b / "HEAD").write_text(OLD); (b / "changes").write_text(changes)
            rc, out = jouer(remote, d, {"FAIL": fail, "SHOWMIG": showmig})
            head = (b / "HEAD").read_text().strip()
        if rc != 0 and "ROLLBACK" not in out:
            sans_rollback.append(nom + (" (code laissé sur NEW)" if head == NEW else " (rien touché)"))
    bloc = re.search(r"if \(\$deployExitCode -ne 0\) \{(.*?)\n\}", ps1, re.S)
    message_inconditionnel = bool(bloc and "rollback automatique effectue" in bloc.group(1)
                                  and not re.search(r"\bif\b", bloc.group(1), re.I))
    repro = len(sans_rollback) >= 6 and message_inconditionnel
    return {"repro": repro, "observe": (
        f"sorties non nulles SANS rollback : {len(sans_rollback)}/{len(CAS)} -> {sans_rollback} ; "
        f"bloc PowerShell « rollback automatique effectué » pour tout code ≠ 0 : {message_inconditionnel}")}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
