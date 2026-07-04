"""Canonical pipeline stages, loaded from the repo-root STAGES.py (CLAUDE.md #2).

Stage names are NEVER hardcoded here — this module locates and loads the single
source of truth (`STAGES.py` at the repo root) so the CRM Lead model and any
other code share the exact same list. CI (`scripts/check_stages.py`) enforces it.

The loader copes with all run contexts:
  - container: `/opt/STAGES.py` (mounted read-only via docker-compose)
  - host / CI: walks up from this file to the repo root

It is careful NEVER to load *itself*: on a case-insensitive filesystem (Windows
hosts via Docker bind mounts) this file, `stages.py`, also matches the name
`STAGES.py`, so a naive search would recurse into itself.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
from pathlib import Path

_HERE = Path(__file__).resolve()


def _is_self(path: Path) -> bool:
    try:
        return os.path.samefile(path, _HERE)
    except OSError:
        return False


def _load_stages_module():
    # 1) Already importable and complete (guard against empty/partial placeholder).
    try:
        module = importlib.import_module("STAGES")
        if hasattr(module, "STAGES") and hasattr(module, "STAGE_LABELS"):
            return module
    except Exception:
        pass

    # 2) Search known locations for the real STAGES.py, skipping this file.
    candidates = [Path("/opt") / "STAGES.py"]           # docker-compose mount
    candidates += [parent / "STAGES.py" for parent in _HERE.parents]  # repo root (host/CI)
    candidates += [Path("/app") / "STAGES.py", Path.cwd() / "STAGES.py"]

    for cand in candidates:
        try:
            if not cand.exists() or _is_self(cand):
                continue
        except OSError:
            continue
        spec = importlib.util.spec_from_file_location("taqinor_canonical_stages", cand)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "STAGES") and hasattr(module, "STAGE_LABELS"):
            return module

    raise ImportError(
        "Canonical STAGES.py not found. In containers it must be mounted at "
        "/opt/STAGES.py (see docker-compose.yml); on host/CI it is the repo root."
    )


_stages = _load_stages_module()

# Re-exported canonical values.
STAGES = list(_stages.STAGES)
STAGE_LABELS = dict(_stages.STAGE_LABELS)
# Per-stage constants, re-exported from the canonical STAGES.py (rule #2 — never
# hardcode stage keys; import them from here).
NEW = _stages.NEW
CONTACTED = _stages.CONTACTED
QUOTE_SENT = _stages.QUOTE_SENT
FOLLOW_UP = _stages.FOLLOW_UP
SIGNED = _stages.SIGNED
COLD = _stages.COLD
CONVERSION_STAGE = _stages.CONVERSION_STAGE

# Ready-made (key, French label) pairs for Django model `choices`.
STAGE_CHOICES = [(key, STAGE_LABELS[key]) for key in STAGES]
