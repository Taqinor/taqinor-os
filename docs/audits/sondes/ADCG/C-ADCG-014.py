"""Rejoue core/backup.py (copie, Django simulé) : la limite souple Celery levée pendant pg_restore laisse le drill « en_cours » ; la même levée pendant pg_dump finit en « echec »."""
SONDE = {"constat": "C-ADCG-014", "sha": "ce4e5fc4f",
         "attendu": "drill : exception propagée + statut final en_cours ; dump : statut echec ; limite souple globale 120 s, aucune limite propre aux deux tâches"}
import ast, importlib, logging, pathlib, re, shutil, sys, tempfile, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"

class A:  # objet permissif : décorateurs, sérialiseurs, sql.SQL(...)
    def __init__(s, *a, **k): pass
    def __call__(s, *a, **k): return a[0] if len(a) == 1 and callable(a[0]) and not k else A()
    def __getattr__(s, n): return A()


class SoftTimeLimitExceeded(Exception):  # billiard.exceptions.SoftTimeLimitExceeded hérite d'Exception
    pass


def charger(tmp):
    def mod(nom, **attrs):
        m = types.ModuleType(nom); m.__getattr__ = lambda n: A(); m.__dict__.update(attrs); sys.modules[nom] = m
    db = {"NAME": "erp_db", "HOST": "db", "PORT": "5432", "USER": "u", "PASSWORD": "p"}
    mod("django"); mod("django.conf", settings=types.SimpleNamespace(DATABASES={"default": db}, MINIO_ENDPOINT="m",
                                                                     MINIO_ACCESS_KEY="a", MINIO_SECRET_KEY="s"))
    import datetime
    mod("django.utils", timezone=types.SimpleNamespace(now=datetime.datetime.now))
    for n in ("psycopg2", "drf_spectacular", "drf_spectacular.utils", "rest_framework", "rest_framework.decorators",
              "rest_framework.permissions", "rest_framework.response"):
        mod(n)
    pkg = pathlib.Path(tmp) / "core"; pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "data_explorer.py").write_text("def list_datasets(): return []\n")
    (pkg / "models.py").write_text("class BackupRun:\n STATUT_EN_COURS='en_cours'; STATUT_TERMINE='termine'; STATUT_ECHEC='echec'\n")
    shutil.copy(DJ / "core/backup.py", pkg / "backup.py")
    sys.path.insert(0, tmp)
    return importlib.import_module("core.backup")


class Run:
    def __init__(s): s.statut, s.detail, s.pk, s.object_key = "en_attente", {}, 9, ""
    def save(s, **k): pass


def sub(cible):
    def run(args, **k):
        if args[0] == cible: raise SoftTimeLimitExceeded()
        return types.SimpleNamespace(returncode=0, stderr=b"")
    return types.SimpleNamespace(run=run, PIPE=-1)


def sonde(ctx=None):
    logging.disable(50)
    with tempfile.TemporaryDirectory() as tmp:
        b = charger(tmp)
        b._dernier_dump_termine = lambda: types.SimpleNamespace(pk=1, object_key="pg_dumps/x.dump")
        b._minio_client = lambda: types.SimpleNamespace(download_file=lambda *a: None)
        b.subprocess = sub("pg_restore")
        drill, leve = Run(), False
        try:
            b.restore_drill(drill)
        except SoftTimeLimitExceeded:
            leve = True
        b.subprocess = sub("pg_dump"); dump = Run(); b.dump_database(dump)
        sys.path.remove(tmp)
        for n in [n for n in sys.modules if n == "core" or n.startswith("core.")]: del sys.modules[n]
    base = (DJ / "erp_agentique/settings/base.py").read_text(encoding="utf-8")
    souple = int(re.search(r"^CELERY_TASK_SOFT_TIME_LIMIT = (\d+)", base, re.M).group(1))
    arbre = ast.parse((DJ / "core/tasks.py").read_text(encoding="utf-8"))
    propres = {f.name: [kw.arg for d in f.decorator_list if isinstance(d, ast.Call) for kw in d.keywords]
               for f in arbre.body if isinstance(f, ast.FunctionDef) and f.name in ("dump_database_task", "restore_drill_task")}
    sans_limite = not any("time_limit" in (a or "") for v in propres.values() for a in v)
    repro = leve and drill.statut == "en_cours" and sans_limite
    return {"repro": repro, "observe": (
        f"drill : exception propagée={leve}, statut final={drill.statut} ; dump : statut={dump.statut} "
        f"({dump.detail.get('message', '')[:40]}) ; limite souple globale={souple}s ; mots-clés des décorateurs={propres} ; "
        f"marge mesurée prod drill 49-68 s → {souple - 68}-{souple - 49} s")}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
