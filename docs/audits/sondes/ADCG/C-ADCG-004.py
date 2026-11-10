"""Rejoue le healthcheck de deploy-prod.ps1 (commandes factices) et l'agrégat réel de core/health.py : une sonde qui ne s'exécute pas, un showmigrations en échec ou celery/beat morts passent tous au vert."""
SONDE = {"constat": "C-ADCG-004", "sha": "ce4e5fc4f",
         "attendu": "exec du healthcheck en échec -> rc 0 sans rollback ; showmigrations en échec -> UNAPPLIED=0 ; overall_status(cache/broker/beat dégradés) = degraded ; cache Redis mort avec IGNORE_EXCEPTIONS = degraded, jamais down"}
import ast, os, re, shutil, subprocess, tempfile, pathlib
RACINE = pathlib.Path(__file__).resolve().parents[4]
OLD, NEW = "a" * 40, "b" * 40
SHIM = r'''#!/usr/bin/env bash
n=$(basename "$0"); a="$n $*"; echo "$a" >> "$BANC/calls.log"
case "$a" in
 "git rev-parse HEAD") cat "$BANC/HEAD";;
 "git diff --name-only"*) cat "$BANC/changes";;
 "git reset --hard "*) t=$3; [ "$t" = origin/main ] && t=$NEW; echo "$t" > "$BANC/HEAD";;
esac
if [ -n "${FAIL:-}" ] && echo "$a" | grep -qE "$FAIL"; then echo "Traceback: boom" >&2; exit 1; fi
exit 0
'''

def px(p):
    p = str(p).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:", p) else p

def bash():
    g = r"C:\Program Files\Git\bin\bash.exe"
    return g if os.path.exists(g) else shutil.which("bash")

def jouer(texte, fail):
    with tempfile.TemporaryDirectory() as d:
        b = pathlib.Path(d)
        for s in ("bin", "repo", "state"):
            (b / s).mkdir()
        for n in ("git", "docker", "flock"):
            (b / "bin" / n).write_bytes(SHIM.encode())
        (b / "HEAD").write_text(OLD); (b / "changes").write_text("")
        t = texte.replace("/opt/taqinor-os", px(b / "repo")).replace("/opt/autodeploy", px(b / "state"))
        (b / "s.sh").write_bytes(t.replace("\r\n", "\n").encode())
        r = subprocess.run([bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_", px(b / "bin"), px(b / "s.sh")],
                           env={**os.environ, "BANC": px(b), "NEW": NEW, "FAIL": fail}, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120)
        return r.returncode, r.stdout

def fonctions(noms):
    src = (RACINE / "backend/django_core/core/health.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    garde = [n for n in arbre.body if (isinstance(n, ast.FunctionDef) and n.name in noms)
             or (isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id.startswith("STATUS_"))]
    class Cache:  # comportement django-redis IGNORE_EXCEPTIONS=True, Redis mort : set no-op, get None
        def set(self, *a, **k): return None
        def get(self, *a, **k): return None
    class Log:
        def __getattr__(self, n): return lambda *a, **k: None
    ns = {"cache": Cache(), "logger": Log()}
    exec(compile(ast.Module(body=garde, type_ignores=[]), "health.py", "exec"), ns)
    return ns

def sonde(ctx=None):
    ps1 = (RACINE / "scripts/deploy-prod.ps1").read_text(encoding="utf-8")
    remote = "ZERO_DOWNTIME=0\n" + re.search(r"\$remote = @'\r?\n(.*?)\r?\n'@", ps1, re.S).group(1)
    rc_h, out_h = jouer(remote, r"python -c .*health")
    vert_sans_sonde = rc_h == 0 and "ROLLBACK" not in out_h and "Healthcheck post-deploiement: \n" in out_h
    rc_s, out_s = jouer(remote, "showmigrations")
    unapplied_0 = rc_s == 0 and "Migrations non appliquees restantes: 0" in out_s
    ns = fonctions({"overall_status", "_check_cache"})
    agr = ns["overall_status"]([{"name": "database", "status": "ok"}, {"name": "broker", "status": "degraded"},
                                {"name": "beat", "status": "degraded"}, {"name": "queue", "status": "unknown"}])
    cache = ns["_check_cache"]()["status"]
    ignore = bool(re.search(r'"IGNORE_EXCEPTIONS":\s*True', (RACINE / "backend/django_core/erp_agentique/settings/base.py").read_text(encoding="utf-8")))
    agr_cache = ns["overall_status"]([{"name": "database", "status": "ok"}, {"name": "cache", "status": cache}])
    repro = vert_sans_sonde and unapplied_0 and agr != "down" and ignore and cache != "down" and agr_cache != "down"
    return {"repro": repro, "observe": (
        f"healthcheck non exécuté : rc={rc_h}, rollback={'ROLLBACK' in out_h}, statut lu vide={vert_sans_sonde} ; "
        f"showmigrations en échec : rc={rc_s}, UNAPPLIED=0={unapplied_0} ; overall_status(broker+beat dégradés)={agr} ; "
        f"IGNORE_EXCEPTIONS={ignore}, _check_cache Redis mort={cache}, agrégat={agr_cache}")}

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
