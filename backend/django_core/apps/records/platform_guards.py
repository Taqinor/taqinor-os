"""ARC8/ARC26 — pure platform-kernel guard logic (no Django, no DB, no I/O).

Lives inside ``apps/records`` so it is importable both by the CI entry point
``scripts/check_platform.py`` (which adds ``backend/django_core`` to ``sys.path``)
AND by the Django test runner (``apps/records/tests_check_platform.py``) — the
test container only mounts ``backend/django_core``, never ``scripts/``.

These functions are STRING/AST-free text scanners (regex over source text) so
they stay in the fast, DB-free ``stage-names`` CI lane.
"""
from __future__ import annotations

import re

# ── ARC8 — bespoke *Activity chatter classes ──────────────────────────────────

# Matches a model class whose name ends in "Activity" (the chatter shape), e.g.
# ``class LeadActivity(models.Model):``. Column-0 ``class`` only (module level).
ACTIVITY_CLASS_RE = re.compile(
    r"^class\s+([A-Za-z_][A-Za-z0-9_]*Activity)\s*\(([^)]*)\)\s*:",
    re.MULTILINE,
)

# The legacy chatter/activity classes present at ARC8 time (frozen — never
# migrated in this wave). A NEW *Activity model class NOT in this set must use
# the generic ``records.Activity`` instead. Format: "app.ClassName".
GRANDFATHERED_ACTIVITY_CLASSES = frozenset({
    "contrats.ContratActivity",
    "crm.LeadActivity",
    "crm.PlanActivite",
    "crm.EtapePlanActivite",
    "flotte.ActiviteFlotte",
    "ged.DocumentActivity",
    "gestion_projet.ProjetActivity",
    "litiges.ReclamationActivity",
    "rh.DossierActivity",
    "rh.CandidatureActivity",
    "sav.TicketActivity",
    "sav.TicketActiviteAFaire",
    "ventes.DevisActivity",
    "ventes.FactureActivity",
})


def scan_activity_classes(app: str, text: str) -> list[str]:
    """Return NEW ``app.ClassName`` *Activity model classes found in ``text``.

    ``records`` is exempt (it OWNS the generic Activity). A match is reported
    only when its qualified name is NOT grand-fathered and the class subclasses
    a Django ``Model`` (bases mention ``Model``)."""
    if app == "records":
        return []
    found: list[str] = []
    for m in ACTIVITY_CLASS_RE.finditer(text):
        class_name, bases = m.group(1), m.group(2)
        if "Model" not in bases:
            continue  # e.g. a plain helper class, not a Django model
        qualified = f"{app}.{class_name}"
        if qualified not in GRANDFATHERED_ACTIVITY_CLASSES:
            found.append(qualified)
    return found


def activity_error_line(qualified: str) -> str:
    return (
        f"[ARC8] Nouvelle classe modèle « {qualified} » de type *Activity hors "
        f"de apps/records. Le chatter doit converger sur records.Activity "
        f"(records.services.log_activity + ChatterViewSetMixin) — n'ajoutez pas "
        f"un modèle chatter maison. Si c'est un cas légitime NON-chatter, "
        f"ajoutez-le à GRANDFATHERED_ACTIVITY_CLASSES."
    )
