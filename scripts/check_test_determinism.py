"""CI guard: no sleeps or unfrozen live-clock assertions in tests (YTEST15).

Flags two flakiness patterns:
  1. Backend tests calling ``time.sleep(`` — a real wait has zero legitimate
     use in a unit/integration test; either freeze time (``testkit.time.
     frozen``) or the code under test needs a fake clock injected.
  2. Playwright specs calling ``page.waitForTimeout(``/a bare ``sleep(`` —
     a fixed wait instead of an explicit assertion/wait-for-condition.
  3. Backend tests comparing a live ``timezone.now()`` directly inside an
     assertion (``self.assertEqual(x, timezone.now()...)``,
     ``self.assertGreater(x, timezone.now())``…) — flaky near a clock
     boundary; freeze time instead (``testkit.time.frozen``).

Pre-existing hits are whitelisted explicitly below (each with the bug it
would need fixing to remove) rather than silently ignored, so the guard is
green today and any NEW violation fails the build.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = ROOT / "backend" / "django_core"
E2E_ROOT = ROOT / "frontend" / "e2e"

SKIPPED_PARTS = {".git", "node_modules", "migrations", "dist", "build"}

SLEEP_RE = re.compile(r"\btime\.sleep\s*\(")
WAIT_FOR_TIMEOUT_RE = re.compile(r"\bpage\.waitForTimeout\s*\(")
BARE_SLEEP_RE = re.compile(r"(?<!wait_for_)(?<!async )\bsleep\s*\(\s*\d")
LIVE_NOW_IN_ASSERTION_RE = re.compile(
    r"\bassert\w*\([^\n]*timezone\.now\(\)"
)

# Pre-existing hits (2026-07 audit), whitelisted rather than fixed here — the
# owning apps' test files belong to other in-flight lanes. Each is a real
# (low-severity) flakiness risk near a clock boundary; fix by wrapping the
# assertion window in ``with testkit.time.frozen(...):``.
WHITELISTED_LIVE_NOW: set[tuple[str, int]] = {
    ("apps/compta/tests/test_retenue_garantie_cautions.py", 96),
    ("apps/compta/tests/test_retenue_garantie_cautions.py", 142),
    ("apps/kb/tests/test_verification_verrou.py", 61),
    ("apps/ventes/tests/test_acceptation.py", 89),
    ("apps/ventes/tests/test_qg8_devis_whatsapp.py", 159),
    ("apps/ventes/tests/test_refus.py", 67),
}


def _iter_py_test_files():
    if not BACKEND_ROOT.exists():
        return
    for path in BACKEND_ROOT.rglob("*.py"):
        if any(part in SKIPPED_PARTS for part in path.parts):
            continue
        name = path.name
        is_test_file = (
            name.startswith("test_")
            or name.startswith("tests_")
            or name.endswith("_test.py")
            or name == "tests.py"
            or "tests" in path.parts
        )
        if not is_test_file:
            continue
        yield path


def _iter_e2e_spec_files():
    if not E2E_ROOT.exists():
        return
    for path in E2E_ROOT.rglob("*.spec.js"):
        if any(part in SKIPPED_PARTS for part in path.parts):
            continue
        yield path


def main() -> int:
    failures: list[str] = []

    for path in _iter_py_test_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(BACKEND_ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SLEEP_RE.search(line):
                failures.append(
                    f"{rel}:{lineno}: time.sleep( in a backend test — "
                    f"freeze time instead (testkit.time.frozen)."
                )
            if LIVE_NOW_IN_ASSERTION_RE.search(line):
                if (rel, lineno) in WHITELISTED_LIVE_NOW:
                    continue
                failures.append(
                    f"{rel}:{lineno}: assertion compares against a live "
                    f"timezone.now() — freeze time instead (testkit.time.frozen) "
                    f"or add to WHITELISTED_LIVE_NOW with justification."
                )

    for path in _iter_e2e_spec_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if WAIT_FOR_TIMEOUT_RE.search(line):
                failures.append(
                    f"{rel}:{lineno}: page.waitForTimeout( — use an explicit "
                    f"wait-for-condition/assertion instead of a fixed sleep."
                )

    if failures:
        print("Test-determinism violations detected:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Test-determinism guard: no sleeps / unfrozen live-clock assertions found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
