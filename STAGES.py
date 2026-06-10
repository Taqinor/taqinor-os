"""
Canonical pipeline stages — the single source of truth.

Use the English KEYS in code, the French LABELS in the UI. Never hardcode
either. CI (`scripts/check_stages.py`) fails on every push if a stage-list
variable anywhere in the repo diverges from this file.

"Perdu" is NOT a stage. It is a lost-flag with a reason that can be set from
ANY stage. A pipeline item carries `lost=True` + `lost_reason=...` independently
of its current stage.

NOTE — Conversion event marker
==============================
Entering SIGNED is the conversion event of the funnel and is what will later
fire the Meta CAPI "SignedQuote" event (server-side). Any code that transitions
an item INTO SIGNED must call the SignedQuote CAPI emitter. Search this file's
sentinel `SIGNED_QUOTE_CAPI_HOOK` to find every wired call site.
"""
from __future__ import annotations

# Search sentinel — DO NOT REMOVE. Used by integrators to grep for the
# Meta CAPI SignedQuote event hook points.
SIGNED_QUOTE_CAPI_HOOK = "fire on transition INTO SIGNED"

# Canonical stage keys (used in code, DB rows, API payloads).
NEW = "NEW"
CONTACTED = "CONTACTED"
QUOTE_SENT = "QUOTE_SENT"
FOLLOW_UP = "FOLLOW_UP"
SIGNED = "SIGNED"
COLD = "COLD"

# Ordered list — used by lint and UI rendering. The order is the funnel order.
STAGES: list[str] = [
    NEW,
    CONTACTED,
    QUOTE_SENT,
    FOLLOW_UP,
    SIGNED,
    COLD,
]

# French labels for the UI. Keys must match STAGES exactly.
STAGE_LABELS: dict[str, str] = {
    NEW: "Nouveau",
    CONTACTED: "Contacté",
    QUOTE_SENT: "Devis envoyé",
    FOLLOW_UP: "Relance",
    SIGNED: "Signé",
    COLD: "Froid",
}

# Conversion event — entering SIGNED fires the Meta CAPI SignedQuote event.
CONVERSION_STAGE = SIGNED


def label(key: str) -> str:
    """Return the French UI label for a canonical stage key."""
    return STAGE_LABELS[key]
