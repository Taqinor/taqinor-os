"""CI guard (ODX21): module registry ↔ frontend module.config.jsx consistency.

DB-free, mirrors the spirit of ``scripts/check_stages.py``: it scans SOURCE
files textually (no Django setup, no database) so it can run in the fast,
ungated ``stage-names`` CI job.

Checks:

  (a) every backend ``AppConfig`` under ``apps/`` (+ core/authentication) that
      declares a ``module_manifest`` exposes a non-empty ``key``;
  (b) backend module keys are unique (no duplicate ``key`` across apps);
  (c) every frontend ``features/<x>/module.config.jsx`` declares a ``key`` that
      corresponds to a backend manifest key (the reverse is NOT required —
      legacy modules are still hardcoded in the Sidebar, tracked by ODX7).

The deeper live-graph checks (dependencies resolve, no cycle, ModuleToggle keys
are manifest keys) are enforced by the backend test
``core/tests/test_module_registry.py`` under the real test runner.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
FRONTEND_FEATURES = ROOT / "frontend" / "src" / "features"

# Matches `'key': 'stock'` / `"key": "stock"` inside a manifest/config dict.
KEY_RE = re.compile(r"""['"]?key['"]?\s*[:=]\s*['"]([A-Za-z0-9_]+)['"]""")

# A frontend nav-module key may intentionally differ from its backend app key
# (e.g. an "advanced" nav grouping over the same backend app). These documented
# aliases map a frontend module.config key to the backend manifest key it uses.
FRONTEND_KEY_ALIASES = {
    'ged_advanced': 'ged',
    # Nav-groupings frontend batch-4 par-dessus des apps backend existantes
    # (pas de nouvelle app backend) : magasin (casiers/put-away/pick/colisage)
    # + logistique (livraisons/transferts/comptages) = surface `stock` ;
    # workflow (BPM/jobs) = surface `automation`.
    'magasin': 'stock',
    'logistique': 'stock',
    'workflow': 'automation',
    # ARC54 — regroupement nav "admin" (utilisateurs/rôles/console tenants) migré
    # depuis index.jsx vers features/admin/module.config.jsx ; pas de nouvelle app
    # backend, la surface d'administration RBAC vit dans `roles`.
    'admin': 'roles',
}


def backend_manifest_keys() -> dict[str, str]:
    """Return {key: source_file} for every backend module_manifest found."""
    keys: dict[str, str] = {}
    apps_py = list((DJANGO_CORE / "apps").glob("*/apps.py"))
    apps_py += [DJANGO_CORE / "core" / "apps.py",
                DJANGO_CORE / "authentication" / "apps.py"]
    for path in apps_py:
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        if "module_manifest" not in src:
            continue
        # Isolate the module_manifest dict block (best-effort: first key line
        # after the attribute) — the manifest's own `key` is the first `key:`.
        idx = src.index("module_manifest")
        m = KEY_RE.search(src, idx)
        if not m:
            sys.exit(f"[check_modules] {path}: module_manifest without 'key'.")
        key = m.group(1)
        if key in keys:
            sys.exit(
                f"[check_modules] duplicate module key '{key}' "
                f"({keys[key]} and {path}).")
        keys[key] = str(path)
    return keys


def frontend_config_keys() -> dict[str, str]:
    """Return {key: source_file} for every frontend module.config.jsx."""
    keys: dict[str, str] = {}
    for path in FRONTEND_FEATURES.glob("*/module.config.jsx"):
        src = path.read_text(encoding="utf-8")
        m = KEY_RE.search(src)
        if not m:
            sys.exit(f"[check_modules] {path}: module.config without 'key'.")
        keys[m.group(1)] = str(path)
    return keys


def main() -> int:
    backend = backend_manifest_keys()
    if not backend:
        sys.exit("[check_modules] no backend module_manifest found.")
    frontend = frontend_config_keys()

    errors = []
    for key, path in sorted(frontend.items()):
        backend_key = FRONTEND_KEY_ALIASES.get(key, key)
        if backend_key not in backend:
            errors.append(
                f"  frontend '{key}' ({path}) has NO matching backend "
                "manifest key.")
    if errors:
        print("[check_modules] registry <-> frontend mismatch:")
        print("\n".join(errors))
        return 1

    print(
        f"[check_modules] OK - {len(backend)} backend manifests, "
        f"{len(frontend)} frontend module.config, all correlated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
