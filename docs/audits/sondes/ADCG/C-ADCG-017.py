"""Rejoue core/backup.py::restore_drill (copie, Django simulé) sur une restauration VIDE : 0 ligne restaurée, société perdue, et le run finit pourtant « termine »."""
SONDE = {"constat": "C-ADCG-017", "sha": "ce4e5fc4f",
         "attendu": "statut termine avec ecarts_tenant non vide et comptages globaux à 0 (rien ne les compare)"}
import importlib, logging, pathlib, shutil, sys, tempfile, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
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
              "rest_framework.permissions", "rest_framework.response",
              "authentication", "authentication.permissions"):
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


class Cur:
    def __enter__(s): return s
    def __exit__(s, *a): return False
    def execute(s, *a): pass
    def fetchone(s): return (0,)          # chaque table restaurée est VIDE
    def fetchall(s): return []            # aucune ligne pour la société 1


def sonde(ctx=None):
    logging.disable(50)
    with tempfile.TemporaryDirectory() as tmp:
        b = charger(tmp)
        sys.modules["psycopg2"].connect = lambda **k: types.SimpleNamespace(cursor=Cur, close=lambda: None)
        b._dernier_dump_termine = lambda: types.SimpleNamespace(pk=1, object_key="pg_dumps/x.dump",
                                                             termine_le=b.timezone.now())  # ADCG39 : dump récent
        b._minio_client = lambda: types.SimpleNamespace(download_file=lambda *a: None)
        b.subprocess = types.SimpleNamespace(run=lambda a, **k: types.SimpleNamespace(returncode=0, stderr=b""), PIPE=-1)
        b._top_tenants_live = lambda limit=5: {1: 1640}   # prod : société 1 = 1640 lignes live
        b._comptages_live = lambda: {t: 5 for t in b.RESTORE_DRILL_TABLES}  # tables clés peuplées en live
        run = Run(); b.restore_drill(run)
        sys.path.remove(tmp)
        for n in [n for n in sys.modules if n == "core" or n.startswith("core.")]: del sys.modules[n]
    d = run.detail
    repro = run.statut == "termine" and bool(d.get("ecarts_tenant")) and not any(d.get("comptages", {}).values())
    return {"repro": repro, "observe": (
        f"statut={run.statut} ; message={d.get('message')!r} ; comptages={d.get('comptages')} ; "
        f"comptages_par_societe={d.get('comptages_par_societe')} ; ecarts_tenant={d.get('ecarts_tenant')}")}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
