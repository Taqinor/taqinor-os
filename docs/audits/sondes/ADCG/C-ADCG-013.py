"""Rejoue la garde de purge authentication/services.py::artefact_backup_disponible : un « export » sans aucun fichier, ou un dump purgé vieux de deux ans, suffisent à autoriser la purge d'une société."""
SONDE = {"constat": "C-ADCG-013", "sha": "ce4e5fc4f",
         "attendu": "export-comptage (artifact_ref et object_key vides) → True ; dump purgé de 2024 → True"}
import ast, datetime, importlib, logging, pathlib, shutil, sys, tempfile, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"

class A:  # objet permissif : décorateurs, sérialiseurs, sql.SQL(...)
    def __init__(s, *a, **k): pass
    def __call__(s, *a, **k): return a[0] if len(a) == 1 and callable(a[0]) and not k else A()
    def __getattr__(s, n): return A()


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


class QS(list):
    def filter(s, **kw): return QS(r for r in s if all(getattr(r, k) == v for k, v in kw.items()))
    def exclude(s, **kw): return QS(r for r in s if not all(getattr(r, k) == v for k, v in kw.items()))
    def exists(s): return bool(s)


def garde():
    arbre = ast.parse((DJ / "authentication/services.py").read_text(encoding="utf-8"))
    f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "artefact_backup_disponible")
    ns = {}
    exec(compile(ast.Module(body=[f], type_ignores=[]), "services.py", "exec"), ns)
    return ns["artefact_backup_disponible"]


def sonde(ctx=None):
    logging.disable(50)
    with tempfile.TemporaryDirectory() as tmp:
        b = charger(tmp)
        BR = sys.modules["core.models"].BackupRun
        BR.KIND_EXPORT, BR.KIND_DB_DUMP = "export", "db_dump"
        ok = garde()
        export = Run(); export.company, export.kind, export.datasets, export.declenche_par = "C", "export", [], None
        export.artifact_ref = ""
        b.executer_sauvegarde(export)                       # le vrai geste POST core/sauvegardes/
        BR.objects = QS([export]); a = ok("C")
        vieux = Run(); vieux.__dict__.update(kind="db_dump", statut="termine", company=None, object_key="pg_dumps/20240101.dump",
                                             purge_is_deleted=True, termine_le=datetime.datetime(2024, 1, 1))
        BR.objects = QS([vieux]); bb = ok("C")
        sys.path.remove(tmp)
        for n in [n for n in sys.modules if n == "core" or n.startswith("core.")]: del sys.modules[n]
    repro = a and bb and export.artifact_ref == "" and export.object_key == ""
    return {"repro": repro, "observe": (
        f"export : statut={export.statut}, artifact_ref={export.artifact_ref!r}, object_key={export.object_key!r}, "
        f"manifeste={export.manifest.get('total_lignes')} ligne(s) → garde={a} ; dump purgé du 01/01/2024 → garde={bb}")}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
