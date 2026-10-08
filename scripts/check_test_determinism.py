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
ALLOW_FILE = ROOT / "scripts" / "test_determinism_allow.txt"
E2E_SUFFIXES = (".spec.js", ".spec.ts", ".spec.mjs")

SLEEP_RE = re.compile(r"\btime\.sleep\s*\(")
WAIT_FOR_TIMEOUT_RE = re.compile(r"\bpage\.waitForTimeout\s*\(")
# `setTimeout(r, 1000)` bare = an awaited sleep; `test.setTimeout(180_000)` /
# `testInfo.setTimeout(...)` (Playwright test budget, a method call) is NOT.
SET_TIMEOUT_RE = re.compile(r"(?<![.\w])setTimeout\s*\(")
BARE_SLEEP_RE = re.compile(r"(?<!wait_for_)(?<!async )\bsleep\s*\(\s*\d")
LIVE_NOW_IN_ASSERTION_RE = re.compile(
    r"\bassert\w*\([^\n]*timezone\.now\(\)"
)

# Pre-existing hits (2026-07 audit), whitelisted rather than fixed here — the
# owning apps' test files belong to other in-flight lanes. Each is a real
# (low-severity) flakiness risk near a clock boundary; fix by wrapping the
# assertion window in ``with testkit.time.frozen(...):``.
WHITELISTED_LIVE_NOW: set[tuple[str, int]] = {
    ("apps/ventes/tests/test_acceptation.py", 97),  # PV86 — +8 lignes au-dessus (déclaration du scénario), MÊME assertion
    ("apps/ventes/tests/test_qg8_devis_whatsapp.py", 159),
    ("apps/ventes/tests/test_refus.py", 67),
}




def _lire_allow(allow_file: Path) -> set[str]:
    """Base decroissante `fichier :: ligne normalisee` (identite de CONTENU, pas de numero)."""
    if not allow_file.exists():
        return set()
    sortie = set()
    for brut in allow_file.read_text(encoding="utf-8").splitlines():
        ligne = brut.strip()
        if ligne and not ligne.startswith("#"):
            sortie.add(ligne)
    return sortie


def _iter_py_test_files(backend_root: Path):
    if not backend_root.exists():
        return
    for path in backend_root.rglob("*.py"):
        if any(part in SKIPPED_PARTS for part in path.relative_to(backend_root).parts):
            continue
        name = path.name
        is_test_file = (
            name.startswith("test_")
            or name.startswith("tests_")
            or name.endswith("_test.py")
            or name == "tests.py"
            or "tests" in path.relative_to(backend_root).parts
        )
        if not is_test_file:
            continue
        yield path


def _iter_e2e_spec_files(e2e_root: Path):
    if not e2e_root.exists():
        return
    for path in e2e_root.rglob("*"):
        if not path.name.endswith(E2E_SUFFIXES):
            continue
        if any(part in SKIPPED_PARTS for part in path.relative_to(e2e_root).parts):
            continue
        yield path


def scan(root: Path, allow: set[str] | None = None) -> list[str]:
    """Violations sur l'arbre `root` ; `allow` = base decroissante (defaut : le fichier du depot)."""
    backend_root = root / "backend" / "django_core"
    e2e_root = root / "frontend" / "e2e"
    if allow is None:
        allow = _lire_allow(root / "scripts" / "test_determinism_allow.txt")
    failures: list[str] = []
    utilises: set[str] = set()

    def autorise(cle: str) -> bool:
        if cle in allow:
            utilises.add(cle)
            return True
        return False

    for path in _iter_py_test_files(backend_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(backend_root).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SLEEP_RE.search(line) or BARE_SLEEP_RE.search(line):
                if autorise(f"{rel} :: {line.strip()}"):
                    continue
                failures.append(
                    f"{rel}:{lineno}: sleep( in a backend test — "
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

    for path in _iter_e2e_spec_files(e2e_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(root).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if WAIT_FOR_TIMEOUT_RE.search(line) or SET_TIMEOUT_RE.search(line):
                if autorise(f"{rel} :: {line.strip()}"):
                    continue
                failures.append(
                    f"{rel}:{lineno}: page.waitForTimeout( / setTimeout( — use an explicit "
                    f"wait-for-condition/assertion instead of a fixed sleep."
                )

    for cle in sorted(allow - utilises):
        failures.append(
            f"scripts/test_determinism_allow.txt: entree orpheline « {cle} » — "
            f"le site a disparu, retirez la ligne (base decroissante)."
        )
    return failures


def main() -> int:
    failures = scan(ROOT)
    if failures:
        print("Test-determinism violations detected:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Test-determinism guard: no sleeps / unfrozen live-clock assertions found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
