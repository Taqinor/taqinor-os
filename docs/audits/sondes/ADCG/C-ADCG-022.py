"""Rejoue core/health.py::etat_ready (copie, Django simulé) avec Redis tombé (cache IGNORE_EXCEPTIONS → get None, broker injoignable) : health/ready répond 200 « ready »."""
SONDE = {"constat": "C-ADCG-022", "sha": "ce4e5fc4f",
         "attendu": "Redis tombé, DB vivante : code 200, status ready ; aucun healthcheck: dans les deux compose"}
import importlib, logging, pathlib, shutil, sys, tempfile, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"


class CacheMort:  # django_redis avec IGNORE_EXCEPTIONS=True (settings/base.py) : get → None, set → no-op
    def get(s, *a, **k): return None
    def set(s, *a, **k): return None


class Cur:
    def __enter__(s): return s
    def __exit__(s, *a): return False
    def execute(s, q): s.q = q
    def fetchone(s): return (100,) if "max_connections" in s.q else (1,)


def sonde(ctx=None):
    logging.disable(50)
    noms = ("django", "django.core", "django.core.cache", "django.db", "django.conf", "redis", "core")
    garde = {n: sys.modules.get(n) for n in noms}
    for n in noms[:5]:
        sys.modules[n] = types.ModuleType(n)
    sys.modules["django.core.cache"].cache = CacheMort()
    sys.modules["django.db"].connection = types.SimpleNamespace(cursor=Cur)
    sys.modules["django.conf"].settings = types.SimpleNamespace(CELERY_BROKER_URL="redis://redis:6379/0")
    redis = types.ModuleType("redis")

    def injoignable(*a, **k): raise ConnectionError("redis injoignable")
    redis.Redis = types.SimpleNamespace(from_url=injoignable); sys.modules["redis"] = redis
    sys.modules.pop("core", None)
    with tempfile.TemporaryDirectory() as tmp:
        pkg = pathlib.Path(tmp) / "core"; pkg.mkdir(); (pkg / "__init__.py").write_text("")
        for f in ("health.py", "metrics.py"):
            shutil.copy(DJ / "core" / f, pkg / f)
        sys.path.insert(0, tmp)
        try:
            corps, code = importlib.import_module("core.health").etat_ready()
        finally:
            sys.path.remove(tmp)
            for n in [n for n in sys.modules if n.startswith("core.")]: sys.modules.pop(n, None)
            for n, m in garde.items():
                if m is None: sys.modules.pop(n, None)
                else: sys.modules[n] = m
    compose = {f: "healthcheck:" in (RACINE / f).read_text(encoding="utf-8") for f in ("docker-compose.yml", "docker-compose.prod.yml")}
    caddy = "health" in (RACINE / "backend/caddy/Caddyfile").read_text(encoding="utf-8")
    repro = code == 200 and corps.get("status") == "ready"
    return {"repro": repro, "observe": (
        f"Redis tombé : health/ready → {code} {corps} ; healthcheck: dans compose={compose} ; 'health' dans Caddyfile={caddy}")}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
