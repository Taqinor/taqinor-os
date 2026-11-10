"""Rejoue core/backup.py::dump_database (copie, Django simulé) : sans BACKUP_OFFSITE_* la copie hors serveur est « off » ; configurée mais en échec, le run reste « termine » et la copie part en clair."""
SONDE = {"constat": "C-ADCG-012", "sha": "ce4e5fc4f",
         "attendu": "env vide : offsite off + termine ; copie distante en échec : statut termine, offsite echec rangé dans detail ; aucun ExtraArgs de chiffrement"}
import importlib, logging, os, pathlib, shutil, sys, tempfile, types
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


def sonde(ctx=None):
    logging.disable(50)
    cles = ("BACKUP_OFFSITE_ENDPOINT", "BACKUP_OFFSITE_BUCKET", "BACKUP_OFFSITE_ACCESS_KEY", "BACKUP_OFFSITE_SECRET_KEY")
    sauve = {k: os.environ.pop(k, None) for k in cles}
    appels = []

    def distant(cfg):
        def up(*a, **k):
            appels.append(k)
            raise OSError("cible distante injoignable")
        return types.SimpleNamespace(upload_file=up)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            b = charger(tmp)
            b.subprocess = types.SimpleNamespace(run=lambda a, **k: types.SimpleNamespace(returncode=0, stderr=b""), PIPE=-1)
            b._minio_client = lambda: types.SimpleNamespace(head_bucket=lambda **k: None, upload_file=lambda *a, **k: None)
            b._offsite_client = distant
            b.sauvegarder_fichiers = lambda client: {}  # ADCG30 : copie des fichiers simulée (réussie)
            r1 = Run(); b.dump_database(r1)
            os.environ.update({k: "x" for k in cles})
            r2 = Run(); b.dump_database(r2)
            sys.path.remove(tmp)
            for n in [n for n in sys.modules if n == "core" or n.startswith("core.")]: del sys.modules[n]
    finally:
        for k, v in sauve.items():
            os.environ.pop(k, None)
            if v is not None: os.environ[k] = v
    o1, o2 = r1.detail.get("offsite", {}), r2.detail.get("offsite", {})
    chiffre = any("ExtraArgs" in k for k in appels)
    # échec invisible : le message du run ne dit rien de la copie distante en échec
    muet = "EN ÉCHEC" not in (r2.detail.get("message") or "")
    repro = (r1.statut == "termine" and o1.get("status") == "off" and r2.statut == "termine"
             and o2.get("status") == "echec" and not chiffre and muet)
    return {"repro": repro, "observe": (
        f"sans variables : statut={r1.statut}, offsite={o1.get('status')} ; copie distante en échec : statut={r2.statut}, "
        f"offsite={o2.get('status')} ({o2.get('message')}) ; message du run={r2.detail.get('message')!r} ; "
        f"ExtraArgs de chiffrement passés={chiffre}")}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
