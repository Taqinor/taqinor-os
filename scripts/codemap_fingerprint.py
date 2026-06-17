#!/usr/bin/env python3
"""Structural fingerprint guard for ``docs/CODEMAP.md``.

Computes one deterministic SHA-256 over the repository's "structural
surface" -- the files whose change should force a refresh of
``docs/CODEMAP.md`` -- and either stamps that digest into the map
(``--write``) or verifies the stored digest still matches (``--check``,
the default). The check runs inside the required ``stage-names`` CI job,
so a structural change that does not refresh the map blocks the merge.

Structural surface
------------------
* file CONTENTS of: every ``models.py`` and every ``urls.py`` under
  ``backend/``, the root ``STAGES.py``,
  ``backend/django_core/requirements.txt``,
  ``backend/fastapi_ia/requirements.txt``, ``frontend/package.json``,
  ``.github/workflows/ci.yml`` and every file under
  ``frontend/src/router``;
* the sorted list of file PATHS (not contents) under
  ``frontend/src/features`` and ``frontend/src/pages`` -- so adding or
  removing a feature/page flips the fingerprint while editing inside a
  component does not.

Determinism
-----------
Everything is sorted, paths are emitted with forward slashes, and file
contents are newline-normalised (CRLF/CR -> LF) before hashing, so the
digest is identical on a Windows checkout (``core.autocrlf=true``) and a
Linux CI runner. ``docs/CODEMAP.md`` itself and the ``scripts/``
directory never contribute to the fingerprint.

Pure Python standard library; no third-party dependency.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODEMAP = ROOT / "docs" / "CODEMAP.md"

FINGERPRINT_PREFIX = "Structure fingerprint:"
GENERATED_PREFIX = "Generated from commit"

# Directory names that never contribute (vendored / generated / state).
VENDORED = {
    ".git", "node_modules", "__pycache__", "migrations",
    ".venv", ".venv_test", "dist", "build",
}


def _relposix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _keep(path: Path) -> bool:
    """Drop excluded files: CODEMAP itself, scripts/, vendored dirs."""
    rel_parts = path.relative_to(ROOT).parts
    if rel_parts and rel_parts[0] == "scripts":
        return False
    if path.resolve() == CODEMAP.resolve():
        return False
    return not any(part in VENDORED for part in rel_parts)


def _content_files() -> list[Path]:
    """Files whose contents feed the fingerprint (existing only)."""
    backend = ROOT / "backend"
    candidates: list[Path] = []
    candidates += backend.rglob("models.py")
    candidates += backend.rglob("urls.py")
    candidates += [
        ROOT / "STAGES.py",
        backend / "django_core" / "requirements.txt",
        backend / "fastapi_ia" / "requirements.txt",
        ROOT / "frontend" / "package.json",
        ROOT / ".github" / "workflows" / "ci.yml",
    ]
    router = ROOT / "frontend" / "src" / "router"
    if router.is_dir():
        candidates += [p for p in router.rglob("*") if p.is_file()]
    kept = {
        _relposix(p): p
        for p in candidates
        if p.is_file() and _keep(p)
    }
    return [kept[rel] for rel in sorted(kept)]


def _path_only(*dirs: Path) -> list[str]:
    """Sorted relative paths of every file under the given dirs."""
    found: set[str] = set()
    for base in dirs:
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and _keep(path):
                found.add(_relposix(path))
    return sorted(found)


def _normalised(path: Path) -> bytes:
    raw = path.read_bytes()
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def compute_fingerprint() -> str:
    """One SHA-256 over the whole structural surface."""
    lines: list[str] = []
    for path in _content_files():
        digest = hashlib.sha256(_normalised(path)).hexdigest()
        lines.append(f"C {_relposix(path)} {digest}")
    features = ROOT / "frontend" / "src" / "features"
    pages = ROOT / "frontend" / "src" / "pages"
    for rel in _path_only(features):
        lines.append(f"P features {rel}")
    for rel in _path_only(pages):
        lines.append(f"P pages {rel}")
    blob = "\n".join(lines) + "\n"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def read_stored() -> str | None:
    """Return the digest stored in CODEMAP, or None if absent."""
    if not CODEMAP.exists():
        return None
    text = CODEMAP.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith(FINGERPRINT_PREFIX):
            return line[len(FINGERPRINT_PREFIX):].strip()
    return None


def write_fingerprint(value: str) -> None:
    """Insert/replace the fingerprint line under the commit header."""
    if not CODEMAP.exists():
        sys.exit(f"Cannot write fingerprint: {CODEMAP} is missing.")
    new_line = f"{FINGERPRINT_PREFIX} {value}"
    lines = CODEMAP.read_text(encoding="utf-8").split("\n")
    kept = [ln for ln in lines if not ln.startswith(FINGERPRINT_PREFIX)]
    out: list[str] = []
    inserted = False
    for line in kept:
        out.append(line)
        if not inserted and line.startswith(GENERATED_PREFIX):
            out.append(new_line)
            inserted = True
    if not inserted:
        sys.exit(
            "Cannot write fingerprint: no line starting with "
            f"'{GENERATED_PREFIX}' found in {CODEMAP}."
        )
    CODEMAP.write_text("\n".join(out), encoding="utf-8", newline="\n")


_GUIDANCE = (
    "Regenerate docs/CODEMAP.md from the current source, then run:\n"
    "    python scripts/codemap_fingerprint.py --write"
)


def _check() -> int:
    fingerprint = compute_fingerprint()
    stored = read_stored()
    if stored is None:
        print(
            "docs/CODEMAP.md has no 'Structure fingerprint:' line.\n"
            + _GUIDANCE,
            file=sys.stderr,
        )
        return 1
    if stored != fingerprint:
        print(
            "docs/CODEMAP.md is stale: the repository's structural "
            "surface changed but the map was not refreshed.\n"
            + _GUIDANCE
            + f"\n  expected: {fingerprint}\n  stored:   {stored}",
            file=sys.stderr,
        )
        return 1
    print(f"docs/CODEMAP.md fingerprint OK ({fingerprint}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify or write the docs/CODEMAP.md structural "
        "fingerprint.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="compute the fingerprint and stamp it into CODEMAP.md",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="verify the stored fingerprint still matches (default)",
    )
    args = parser.parse_args(argv)
    if args.write:
        fingerprint = compute_fingerprint()
        write_fingerprint(fingerprint)
        print(
            "Wrote structure fingerprint to docs/CODEMAP.md "
            f"({fingerprint})."
        )
        return 0
    return _check()


if __name__ == "__main__":
    sys.exit(main())
