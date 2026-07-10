"""Platform-kernel CI guards (Groupe ARC) — DB-free source scan.

Mirrors the spirit of ``scripts/check_stages.py`` / ``scripts/check_modules.py``:
it scans SOURCE files TEXTUALLY (no Django setup, no database) so it can run in
the fast, ungated ``stage-names`` CI job. (Wiring this into CI is ARC52 — this
file only PROVIDES the checks.)

The pure detection logic lives in ``apps/records/platform_guards.py`` so it is
importable BOTH here (CI entry point, run from repo root) AND by the Django test
runner — the test container only mounts ``backend/django_core``, never
``scripts/``. This module adds ``backend/django_core`` to ``sys.path`` to reuse
that single source of truth.

Checks
------
ARC8 — no NEW bespoke ``*Activity`` chatter model outside ``apps/records``: the
    13 near-identical ``*Activity`` classes are frozen legacy; any NEW chatter
    must converge on the generic ``records.Activity``.

Run
---
    python scripts/check_platform.py            # exits non-zero on a violation
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"

# Reuse the single source of truth for the pure guard logic.
if str(DJANGO_CORE) not in sys.path:
    sys.path.insert(0, str(DJANGO_CORE))
from apps.records.platform_guards import (  # noqa: E402
    activity_error_line,
    scan_activity_classes,
)


def _app_of(models_path: Path) -> str:
    """apps/<app>/models.py -> '<app>' (or the parent dir name for a package)."""
    rel = models_path.relative_to(APPS_DIR)
    return rel.parts[0]


def _iter_model_files():
    """Yield every models.py (or models/ package file) under apps/."""
    yield from APPS_DIR.glob("*/models.py")
    yield from APPS_DIR.glob("*/models/*.py")


def find_new_activity_classes() -> list[str]:
    """Return ['app.ClassName', …] for NEW *Activity model classes on disk."""
    violations: list[str] = []
    for path in _iter_model_files():
        app = _app_of(path)
        text = path.read_text(encoding="utf-8")
        violations.extend(scan_activity_classes(app, text))
    return violations


def check_activity_convergence() -> list[str]:
    """ARC8 guard — returns a list of human-readable error lines (empty = OK)."""
    return [activity_error_line(q) for q in sorted(find_new_activity_classes())]


def run_checks() -> list[str]:
    """Run all platform guards; return the flat list of error lines."""
    errors: list[str] = []
    errors.extend(check_activity_convergence())
    return errors


def main() -> int:
    errors = run_checks()
    if errors:
        print("check_platform: VIOLATIONS")
        for line in errors:
            print("  - " + line)
        return 1
    print("check_platform: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
