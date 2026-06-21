# flake8: noqa
"""Shared installation-photo library for the quote covers.

Picks the real installation photo whose power (kWc) is NEAREST the quote,
preferring the same market mode. Agricole has no dedicated farm photos yet, so it
falls back to a residential / industriel / commercial photo of similar power
(founder decision 2026-06-21). Residential likewise picks the nearest-power photo
instead of a single fixed hero.

Library: drop JPEG photos in ``assets/installations/`` named
``<mode>-<kwc>.jpg`` — e.g. ``residentiel-5.4.jpg``, ``industriel-30.jpg``,
``agricole-10.jpg``. ``<mode>`` is optional; ``<kwc>`` is the system size in kWc.
A photo with no parseable kWc/mode (e.g. ``default.jpg``) is the universal
fallback. JPEG only (the covers embed it as image/jpeg). Empty library → "" and
each cover keeps its own bundled fallback.
"""
from __future__ import annotations
import base64
import re
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "assets" / "installations"
_MODES = ("residentiel", "industriel", "commercial", "agricole")


def _entries():
    out = []
    if not _DIR.exists():
        return out
    for p in sorted(_DIR.iterdir()):
        if p.suffix.lower() not in (".jpg", ".jpeg"):
            continue
        stem = p.stem.lower()
        mode = next((m for m in _MODES if m in stem), None)
        m = re.search(r"(\d+(?:[.,]\d+)?)", stem)
        kwc = float(m.group(1).replace(",", ".")) if m else None
        out.append({"path": p, "mode": mode, "kwc": kwc})
    return out


def _score(e, kwc, mode):
    """Lower is better: (mode-preference, kWc-distance)."""
    em = e["mode"]
    if mode and em == mode:
        mp = 0
    elif mode == "agricole" and em in ("residentiel", "industriel", "commercial"):
        mp = 1
    elif em is None:
        mp = 2                      # universal fallback photo
    else:
        mp = 3                      # a different specific mode
    ek = e["kwc"]
    try:
        kd = abs(ek - float(kwc)) if (ek is not None and kwc) else 1e6
    except (TypeError, ValueError):
        kd = 1e6
    return (mp, kd)


def pick_b64(kwc=None, mode=None) -> str:
    """Base64 JPEG of the best-matching installation photo, or "" if none."""
    ents = _entries()
    if not ents:
        return ""
    best = min(ents, key=lambda e: _score(e, kwc, mode))
    try:
        return base64.b64encode(best["path"].read_bytes()).decode()
    except Exception:  # noqa: BLE001 — a cover must never break on a bad file
        return ""
